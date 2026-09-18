// Package proxy 提供上游出口代理池管理。
// 仿照 flex.ai go_backend 的代理池设计：支持 http/socks5/direct 三种类型，
// 文件持久化、轮询/随机选择、健康检查（延迟测量 + 自动剔除失效代理）。
// 用于解决本机 DNS 劫持 / 直连被墙时上游不可达的问题。
package proxy

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"golang.org/x/net/proxy"
)

// Type 代理类型。
type Type string

const (
	HTTP    Type = "http"
	HTTPS   Type = "https"
	SOCKS5  Type = "socks5"
	SOCKS5H Type = "socks5h"
	Direct  Type = "direct"
)

// Item 单个代理。
type Item struct {
	ID             string    `json:"id"`
	Type           Type      `json:"type"`
	Addr           string    `json:"addr"` // host:port（无 scheme）
	Username       string    `json:"username,omitempty"`
	Password       string    `json:"password,omitempty"`
	Enabled        bool      `json:"enabled"`
	Latency        int       `json:"latency_ms"` // 最近一次探测延迟，-1=未知/失败
	LastCheck      time.Time `json:"last_check,omitempty"`
	Failures       int       `json:"failures"` // 连续失败次数
	DisabledReason string    `json:"disabled_reason,omitempty"`
	AddedAt        time.Time `json:"added_at,omitempty"`
}

// Masked 脱敏地址（不暴露密码）。
func (p *Item) Masked() string {
	if p.Username != "" {
		return p.Username + "@" + p.Addr
	}
	return p.Addr
}

// URL 构造代理 URL（用于 transport 配置）。
func (p *Item) URL() *url.URL {
	u := &url.URL{Scheme: string(p.Type), Host: p.Addr}
	if p.Username != "" {
		u.User = url.UserPassword(p.Username, p.Password)
	}
	return u
}

// Pool 代理池。
type Pool struct {
	mu       sync.Mutex
	items    []*Item
	filePath string
	rr       int

	directTransport *http.Transport // 直连 transport（走系统代理环境变量）

	stopCh  chan struct{}
	stopped chan struct{}
}

// NewPool 创建代理池并从文件加载。
func NewPool(filePath string) *Pool {
	p := &Pool{
		filePath:        filePath,
		directTransport: &http.Transport{Proxy: http.ProxyFromEnvironment},
		stopCh:          make(chan struct{}),
		stopped:         make(chan struct{}),
	}
	p.load()
	if len(p.items) == 0 {
		p.items = []*Item{}
	}
	return p
}

// load 从文件加载代理列表。
func (p *Pool) load() {
	b, err := os.ReadFile(p.filePath)
	if err != nil {
		return
	}
	var items []*Item
	if json.Unmarshal(b, &items) == nil {
		p.items = items
	}
}

// save 持久化到文件（原子写）。
func (p *Pool) save() error {
	if p.filePath == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(p.filePath), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(p.items, "", "  ")
	if err != nil {
		return err
	}
	tmp := p.filePath + ".tmp"
	if err := os.WriteFile(tmp, b, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, p.filePath)
}

// List 返回代理列表副本。
func (p *Pool) List() []*Item {
	p.mu.Lock()
	defer p.mu.Unlock()
	out := make([]*Item, len(p.items))
	for i, it := range p.items {
		cp := *it
		out[i] = &cp
	}
	return out
}

// Count 返回代理总数。
func (p *Pool) Count() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.items)
}

// Add 添加代理（自动生成 ID），默认启用，持久化。
func (p *Pool) Add(it Item) error {
	if strings.TrimSpace(it.Addr) == "" {
		return errors.New("缺少代理地址 addr")
	}
	if it.Type == "" {
		it.Type = HTTP
	}
	switch it.Type {
	case HTTP, HTTPS, SOCKS5, SOCKS5H, Direct:
	default:
		return fmt.Errorf("不支持的代理类型: %s", it.Type)
	}
	if it.Type != Direct {
		if !strings.Contains(it.Addr, ":") {
			return errors.New("代理地址格式应为 host:port")
		}
	}
	it.ID = randomID()
	if it.AddedAt.IsZero() {
		it.AddedAt = time.Now()
	}
	if it.Latency == 0 {
		it.Latency = -1
	}
	it.Enabled = true
	p.mu.Lock()
	p.items = append(p.items, &it)
	err := p.save()
	p.mu.Unlock()
	return err
}

// Update 更新代理字段。
func (p *Pool) Update(id string, it Item) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	for _, x := range p.items {
		if x.ID == id {
			it.ID = id
			it.AddedAt = x.AddedAt
			*x = it
			return p.save()
		}
	}
	return fmt.Errorf("代理不存在: %s", id)
}

// Delete 删除代理。
func (p *Pool) Delete(id string) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	for i, x := range p.items {
		if x.ID == id {
			p.items = append(p.items[:i], p.items[i+1:]...)
			return p.save()
		}
	}
	return nil
}

// SetEnabled 启用/停用代理。
func (p *Pool) SetEnabled(id string, enabled bool) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	for _, x := range p.items {
		if x.ID == id {
			x.Enabled = enabled
			if enabled {
				x.Failures = 0
				x.DisabledReason = ""
			}
			return p.save()
		}
	}
	return fmt.Errorf("代理不存在: %s", id)
}

// Enabled 返回启用的代理列表（不区分健康状态）。
func (p *Pool) Enabled() []*Item {
	p.mu.Lock()
	defer p.mu.Unlock()
	var out []*Item
	for _, it := range p.items {
		if it.Enabled {
			cp := *it
			out = append(out, &cp)
		}
	}
	return out
}

// Best 返回延迟最低的健康代理；无可用代理时返回 nil。
// 规则：Enabled 且 Failures==0；优先 Latency>0（有实测健康记录）的，
// 取延迟最小值；全部 Latency 未知时才回退轮询。
func (p *Pool) Best() *Item {
	p.mu.Lock()
	defer p.mu.Unlock()
	var candidates []*Item
	for _, it := range p.items {
		if it.Enabled && it.Failures == 0 {
			candidates = append(candidates, it)
		}
	}
	if len(candidates) == 0 {
		return nil
	}
	// 优先已知延迟（Latency>0）的代理
	var known []*Item
	for _, it := range candidates {
		if it.Latency > 0 {
			known = append(known, it)
		}
	}
	if len(known) > 0 {
		best := known[0]
		for _, it := range known[1:] {
			if it.Latency < best.Latency {
				best = it
			}
		}
		return best
	}
	// 全部延迟未知，轮询
	p.rr = (p.rr + 1) % len(candidates)
	return candidates[p.rr]
}

// RoundRobin 轮询选择一个启用代理。
func (p *Pool) RoundRobin() *Item {
	p.mu.Lock()
	defer p.mu.Unlock()
	var enabled []*Item
	for _, it := range p.items {
		if it.Enabled {
			enabled = append(enabled, it)
		}
	}
	if len(enabled) == 0 {
		return nil
	}
	p.rr = (p.rr + 1) % len(enabled)
	return enabled[p.rr]
}

// transportFor 为单个代理构造 RoundTripper（仿 flex gateway.transportFor）。
func transportFor(it *Item) (http.RoundTripper, error) {
	switch it.Type {
	case HTTP, HTTPS:
		u := it.URL()
		return &http.Transport{Proxy: http.ProxyURL(u)}, nil
	case SOCKS5, SOCKS5H:
		host := it.Addr
		var auth *proxy.Auth
		if it.Username != "" {
			pw := it.Password
			auth = &proxy.Auth{User: it.Username, Password: pw}
		}
		dialer, err := proxy.SOCKS5("tcp", host, auth, proxy.Direct)
		if err != nil {
			return nil, fmt.Errorf("socks5 dialer: %v", err)
		}
		tr := &http.Transport{}
		if cd, ok := dialer.(interface {
			DialContext(ctx context.Context, network, addr string) (net.Conn, error)
		}); ok {
			tr.DialContext = cd.DialContext
		} else {
			tr.Dial = dialer.Dial
		}
		return tr, nil
	default:
		return nil, fmt.Errorf("不支持的代理类型: %s", it.Type)
	}
}

// DirectTransport 直连 transport（走系统代理环境变量，与 flex 一致）。
func (p *Pool) DirectTransport() http.RoundTripper {
	return p.directTransport
}

// Transport 按优先级返回出口 transport（仿 flex gateway.clientFor）：
// 1. globalProxy（UPSTREAM_PROXY，socks5:// 或 http://，账号级/全局显式配置）优先
// 2. 否则代理池中延迟最低的健康代理
// 3. 都没有则直连（ProxyFromEnvironment，走系统代理环境变量）
func (p *Pool) Transport(globalProxy string) http.RoundTripper {
	if g := strings.TrimSpace(globalProxy); g != "" {
		u, err := url.Parse(g)
		if err == nil {
			switch strings.ToLower(u.Scheme) {
			case "http", "https":
				return &http.Transport{Proxy: http.ProxyURL(u)}
			case "socks5", "socks5h":
				var auth *proxy.Auth
				if u.User != nil {
					pw, _ := u.User.Password()
					auth = &proxy.Auth{User: u.User.Username(), Password: pw}
				}
				dialer, err := proxy.SOCKS5("tcp", u.Host, auth, proxy.Direct)
				if err == nil {
					tr := &http.Transport{}
					if cd, ok := dialer.(interface {
						DialContext(ctx context.Context, network, addr string) (net.Conn, error)
					}); ok {
						tr.DialContext = cd.DialContext
					} else {
						tr.Dial = dialer.Dial
					}
					return tr
				}
			}
		}
		// 全局代理解析失败则回落到池/直连
	}
	return p.Select()
}

// Select 按优先级返回出口 transport：
// 优先代理池中延迟最低的健康代理，否则直连（ProxyFromEnvironment）。
func (p *Pool) Select() http.RoundTripper {
	it := p.Best()
	if it == nil || it.Type == Direct {
		return p.directTransport
	}
	tr, err := transportFor(it)
	if err != nil {
		return p.directTransport
	}
	return tr
}

// checkOne 探测单个代理的连通性与延迟（GET probeURL，任何响应都算通，网络错误算失败）。
func (p *Pool) checkOne(it *Item, probeURL string) (latency time.Duration, err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	start := time.Now()
	var client *http.Client
	if it.Type == Direct {
		client = &http.Client{Transport: p.directTransport}
	} else {
		tr, terr := transportFor(it)
		if terr != nil {
			return 0, terr
		}
		client = &http.Client{Transport: tr}
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, probeURL, nil)
	if err != nil {
		return 0, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
	return time.Since(start), nil
}

// CheckAll 对全部启用代理做一次健康检查，返回结果列表（含探测失败信息）。
func (p *Pool) CheckAll(probeURL string) []CheckResult {
	if probeURL == "" {
		probeURL = "https://api.mistral.ai/v1/models"
	}
	items := p.Enabled()
	results := make([]CheckResult, 0, len(items)+1)

	// 直连作为参照
	if dc, err := p.checkDirect(probeURL); err == nil {
		results = append(results, CheckResult{
			ID: "direct", Type: Direct, Addr: "direct", Enabled: true,
			Latency: int(dc.Milliseconds()), LastCheck: time.Now(), OK: true,
		})
	}

	for _, it := range items {
		res := CheckResult{
			ID: it.ID, Type: it.Type, Addr: it.Addr, Enabled: it.Enabled,
			LastCheck: time.Now(),
		}
		lat, err := p.checkOne(it, probeURL)
		if err != nil {
			res.OK = false
			res.Error = err.Error()
			res.Latency = -1
			p.mu.Lock()
			it.Failures++
			it.Latency = -1
			if it.Failures >= 3 {
				it.Enabled = false
				it.DisabledReason = fmt.Sprintf("连续失败 %d 次: %s", it.Failures, err.Error())
			}
			err = p.save()
			p.mu.Unlock()
			if err != nil {
				res.Error += " (save: " + err.Error() + ")"
			}
			res.Failures = it.Failures
			res.DisabledReason = it.DisabledReason
		} else {
			res.OK = true
			res.Latency = int(lat.Milliseconds())
			p.mu.Lock()
			it.Failures = 0
			it.Latency = int(lat.Milliseconds())
			it.LastCheck = time.Now()
			err = p.save()
			p.mu.Unlock()
			if err != nil {
				res.Error = "save: " + err.Error()
			}
		}
		results = append(results, res)
	}
	return results
}

// checkDirect 直连探测（走系统代理环境变量）。
func (p *Pool) checkDirect(probeURL string) (time.Duration, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	start := time.Now()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, probeURL, nil)
	if err != nil {
		return 0, err
	}
	resp, err := (&http.Client{Transport: p.directTransport}).Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
	return time.Since(start), nil
}

// CheckResult 单次健康检查结果。
type CheckResult struct {
	ID             string    `json:"id"`
	Type           Type      `json:"type"`
	Addr           string    `json:"addr"`
	Enabled        bool      `json:"enabled"`
	OK             bool      `json:"ok"`
	Latency        int       `json:"latency_ms"`
	Error          string    `json:"error,omitempty"`
	Failures       int       `json:"failures"`
	DisabledReason string    `json:"disabled_reason,omitempty"`
	LastCheck      time.Time `json:"last_check"`
}

// StartHealthChecker 启动后台健康检查（interval 间隔，probeURL 探测目标）。
func (p *Pool) StartHealthChecker(interval time.Duration, probeURL string) {
	go func() {
		defer close(p.stopped)
		if interval <= 0 {
			interval = 5 * time.Minute
		}
		t := time.NewTicker(interval)
		defer t.Stop()
		for {
			select {
			case <-p.stopCh:
				return
			case <-t.C:
				p.CheckAll(probeURL)
			}
		}
	}()
}

// StopHealthChecker 停止后台健康检查。
func (p *Pool) StopHealthChecker() {
	select {
	case <-p.stopCh:
		return
	default:
		close(p.stopCh)
	}
	<-p.stopped
}

func randomID() string {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(b)
}

// Math 引用，避免误删（Latency 用 int 毫秒，保留精度逻辑）。
var _ = math.MaxInt