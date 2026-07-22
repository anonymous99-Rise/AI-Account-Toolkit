#!/usr/bin/env python3
"""纯协议 ChatGPT 注册（Outlook 邮箱版）。

用 Outlook 4 段接码账号 + 纯 HTTP 协议（curl_cffi + sentinel PoW + IMAP）
直接走 OpenAI authorize 状态机，无浏览器、无 Camoufox、无 Playwright。

接码账号 4 段格式（用 ---- 分隔）：
    email----password----client_id----microsoft_refresh_token

用法：
    python register_outlook.py 'xxx@outlook.jp----<pwd>----<client_id>----M.C538_...'

可选环境变量：
    PROXY                出口代理 URL，例如 socks5://user:pass@host:port
    OTP_TIMEOUT          OTP 等待秒数（默认 60，下限 30）
    WEBUI_ALLOW_LOGIN    1 = 邮箱被 OpenAI 识为已注册时走 OTP login 拿凭证
                         (默认 0：fast-fail 抛 RuntimeError，换下一个号)
    SKIP_OAUTH_TOKEN_EXCHANGE  1=跳过 OAuth refresh_token 交换
    OPENAI_SENTINEL_DISABLE_QUICKJS  1=禁用 QuickJS sentinel（仅纯 Python PoW）
    AUTH_HTTP_TRACE      1=打印每次 HTTP 请求详情（调试用）
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402
from mail_outlook import OutlookMailProvider  # noqa: E402
from auth_flow import AuthFlow  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python register_outlook.py "
            "'email----password----client_id----refresh_token'",
            file=sys.stderr,
        )
        sys.exit(2)

    parts = sys.argv[1].split("----")
    if len(parts) != 4:
        print(f"4 段格式错: 拿到 {len(parts)} 段", file=sys.stderr)
        sys.exit(2)
    email, password, client_id, refresh = parts
    logger.info(
        f"账号: {email}  client_id={client_id[:8]}…  refresh_token len={len(refresh)}"
    )

    cfg = Config()
    cfg.proxy = os.environ.get("PROXY") or None

    mail = OutlookMailProvider(
        email=email, password=password,
        client_id=client_id, refresh_token=refresh,
    )

    flow = AuthFlow(cfg)
    logger.info("[auth_flow] run_register 启动 (纯协议 + outlook IMAP) ...")
    partial = False
    try:
        result = flow.run_register(mail)
        d = result.to_dict()
    except RuntimeError as e:
        # 拿到部分凭证（access_token / refresh_token 任一）也算成功，保留下来
        d = flow.result.to_dict()
        if d.get("access_token") or d.get("refresh_token") or d.get("session_token"):
            partial = True
            logger.warning(f"[register] 流程异常: {e}")
            logger.warning("[register] 但已拿到部分凭证，继续保存")
        else:
            raise

    logger.info(
        f"[register] 完成 email={d.get('email')} "
        f"access_token=len{len(d.get('access_token') or '')} "
        f"session_token=len{len(d.get('session_token') or '')} "
        f"refresh_token=len{len(d.get('refresh_token') or '')}"
    )

    out_path = ROOT / f"account_{email.replace('@', '_at_')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    tag = " (部分凭证, 缺 session_token / 可能因为账号需要补手机)" if partial else ""
    print(f"\n=== DONE{tag} ===\n账号凭证已写入: {out_path}")


if __name__ == "__main__":
    main()
