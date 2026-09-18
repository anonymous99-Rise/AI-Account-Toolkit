package keys

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// Entry 上游 key 池中的一条记录。
type Entry struct {
	Key           string    `json:"key"`
	Source        string    `json:"source"`          // env / registered:<email> / seed
	AddedAt       time.Time `json:"added_at"`
	Healthy       bool      `json:"healthy"`
	LastError     string    `json:"last_error,omitempty"`
	CooldownUntil time.Time `json:"cooldown_until,omitempty"` // 冷却期内不参与轮询
}

func (e *Entry) Masked() string {
	if len(e.Key) <= 10 {
		return "******"
	}
	return e.Key[:5] + "…" + e.Key[len(e.Key)-4:]
}

// Available 是否处于可用状态（未进入冷却）。
func (e *Entry) Available() bool {
	if e == nil {
		return false
	}
	now := time.Now()
	return e.CooldownUntil.IsZero() || now.After(e.CooldownUntil)
}

// fileState 是 data/keys.json 的磁盘格式。
type fileState struct {
	UpstreamKeys []*Entry `json:"upstream_keys"`
	LocalKeys    []string `json:"local_keys"`
}

// Pool 管理上游 key 池（轮询 + 失败冷却）与本地鉴权 key。
type Pool struct {
	mu       sync.Mutex
	filePath string
	upstream []*Entry
	local    []string
	rr       int
}

func NewPool(filePath string) *Pool {
	p := &Pool{filePath: filePath}
	if b, err := os.ReadFile(filePath); err == nil {
		var st fileState
		if json.Unmarshal(b, &st) == nil {
			p.upstream = st.UpstreamKeys
			p.local = st.LocalKeys
		}
	}
	if p.upstream == nil {
		p.upstream = []*Entry{}
	}
	if p.local == nil {
		p.local = []string{}
	}
	return p
}

// AddUpstream 加入上游 key（去重），并持久化。
func (p *Pool) AddUpstream(key, source string) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	for _, e := range p.upstream {
		if e.Key == key {
			return p.saveLocked()
		}
	}
	p.upstream = append(p.upstream, &Entry{
		Key: key, Source: source, AddedAt: time.Now(), Healthy: true,
	})
	return p.saveLocked()
}

// RemoveUpstream 删除上游 key，并持久化。
func (p *Pool) RemoveUpstream(key string) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	for i, e := range p.upstream {
		if e.Key == key {
			p.upstream = append(p.upstream[:i], p.upstream[i+1:]...)
			return p.saveLocked()
		}
	}
	return fmt.Errorf("key 不存在")
}

// AddLocal 注册一个本地鉴权 key，持久化。
func (p *Pool) AddLocal(key string) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	for _, k := range p.local {
		if k == key {
			return nil
		}
	}
	p.local = append(p.local, key)
	return p.saveLocked()
}

// RemoveLocal 删除一个本地鉴权 key，持久化。
func (p *Pool) RemoveLocal(key string) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	for i, k := range p.local {
		if k == key {
			p.local = append(p.local[:i], p.local[i+1:]...)
			return p.saveLocked()
		}
	}
	return fmt.Errorf("本地 key 不存在: %s", key)
}

// EnsureLocalKey 保证至少存在一个本地 key；没有就生成并持久化。
func (p *Pool) EnsureLocalKey() string {
	p.mu.Lock()
	defer p.mu.Unlock()
	if len(p.local) > 0 {
		return p.local[0]
	}
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		panic("无法生成随机 key: " + err.Error())
	}
	key := hex.EncodeToString(buf)
	p.local = append(p.local, key)
	_ = p.saveLocked()
	return key
}

// ValidLocal 常量时间比较，校验客户端提供的本地 key。
func (p *Pool) ValidLocal(key string) bool {
	if key == "" {
		return false
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	for _, k := range p.local {
		if subtle.ConstantTimeCompare([]byte(k), []byte(key)) == 1 {
			return true
		}
	}
	return false
}

// PickUpstream 轮询选出一个可用的上游 key；全部冷却时兜底重试最早过期的那个。
func (p *Pool) PickUpstream() *Entry {
	p.mu.Lock()
	defer p.mu.Unlock()
	var avail []*Entry
	for _, e := range p.upstream {
		if e.Available() {
			avail = append(avail, e)
		}
	}
	if len(avail) == 0 {
		avail = p.upstream
	}
	if len(avail) == 0 {
		return nil
	}
	i := p.rr % len(avail)
	p.rr++
	return avail[i]
}

// ReportFailure 记录一次上游失败，按状态码设置冷却时间（内存态，不落盘以免热路径 IO）。
func (p *Pool) ReportFailure(e *Entry, status int, msg string) {
	if e == nil {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	d := 30 * time.Second
	switch status {
	case 401, 402, 403:
		d = 30 * time.Minute // key 无效/欠费，长冷却
	case 429:
		d = 60 * time.Second // 限流
	}
	e.Healthy = false
	e.LastError = msg
	e.CooldownUntil = time.Now().Add(d)
}

func (p *Pool) ReportSuccess(e *Entry) {
	if e == nil {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	e.Healthy = true
	e.LastError = ""
	e.CooldownUntil = time.Time{}
}

// KeyInfo / Snapshot 用于 /api/keys 状态展示。
type KeyInfo struct {
	Masked        string    `json:"masked_key"`
	Source        string    `json:"source"`
	Healthy       bool      `json:"healthy"`
	LastError     string    `json:"last_error,omitempty"`
	AddedAt       time.Time `json:"added_at"`
	CooldownUntil time.Time `json:"cooldown_until,omitempty"`
}

type Snapshot struct {
	LocalKeys []string  `json:"local_keys"`
	Upstream  []KeyInfo `json:"upstream"`
}

func (p *Pool) Snapshot() Snapshot {
	p.mu.Lock()
	defer p.mu.Unlock()
	s := Snapshot{LocalKeys: append([]string(nil), p.local...)}
	for _, e := range p.upstream {
		s.Upstream = append(s.Upstream, KeyInfo{
			Masked: e.Masked(), Source: e.Source, Healthy: e.Healthy,
			LastError: e.LastError, AddedAt: e.AddedAt, CooldownUntil: e.CooldownUntil,
		})
	}
	return s
}

func (p *Pool) UpstreamCount() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.upstream)
}

func (p *Pool) saveLocked() error {
	if p.filePath == "" {
		return nil
	}
	dir := filepath.Dir(p.filePath)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	st := fileState{UpstreamKeys: p.upstream, LocalKeys: p.local}
	b, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	tmp := p.filePath + ".tmp"
	if err := os.WriteFile(tmp, b, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, p.filePath)
}