package web

import (
	"embed"
	"html/template"
	"io/fs"
	"net/http"
)

//go:embed templates
var embedFS embed.FS

var indexTpl = template.Must(template.ParseFS(embedFS, "templates/index.html"))
var loginTpl = template.Must(template.ParseFS(embedFS, "templates/login.html"))

// Index 渲染 Playground 主页面（使用 html/template，轻量无重型框架）。
func Index(adminPasswordSet bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_ = indexTpl.Execute(w, struct {
			Name            string
			NoAdminPassword bool
		}{
			Name:            "Mistral Console Proxy",
			NoAdminPassword: !adminPasswordSet,
		})
	}
}

// Static 提供嵌入式静态资源（styles.css / app.js）。
func Static() http.Handler {
	sub, err := fs.Sub(embedFS, "templates")
	if err != nil {
		panic(err)
	}
	return http.FileServerFS(sub)
}
