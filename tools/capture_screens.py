"""自动截图：逐角色登录，逐页面截图（含应急状态对比），输出到 docs/screenshots/

前置：后端已在 127.0.0.1:8000 运行且数据库已 seed（v4：4账号，无学生账号）。
"""
import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

# 环境里 headless-shell 未下载完成，直接用完整版 chrome.exe
_CHROME = os.path.expandvars(
    r"%LOCALAPPDATA%\ms-playwright\chromium-1228\chrome-win64\chrome.exe")

# 每个角色要截的页面：(导航页key, 截图文件名)
ROLE_PAGES = {
    "admin": ["dashboard", "matrix", "workbench", "assets", "inspections", "spaces"],
    "teacher": ["inbox", "leaveadmin", "spaces", "venues", "inspections", "report"],
    "parent": ["child", "courses", "leave", "meals", "inbox", "travel", "canteen", "report"],
    "community": ["workbench", "hazards", "approvals"],
}


async def shot(page, name):
    await page.wait_for_timeout(900)
    await page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print(f"  截图 {name}.png")


async def login_as(page, username):
    await page.goto(BASE, wait_until="networkidle")
    await page.wait_for_selector(f".acct[onclick*=\"{username}\"]", timeout=8000)
    await page.click(f".acct[onclick*=\"{username}\"]")
    await page.wait_for_selector("nav button", timeout=8000)
    await page.wait_for_timeout(700)


async def goto_nav(page, key):
    await page.click(f"nav button[data-page='{key}']")
    await page.wait_for_timeout(900)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=_CHROME)
        page = await browser.new_page(viewport={"width": 1440, "height": 960})

        # 0. 登录页
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_selector(".acct", timeout=8000)
        await shot(page, "00_login")

        # 1. 先确保系统处于常态
        await page.request.post(BASE + "/api/brain/plan/reset")

        # 2. 逐角色常态页面
        for role, keys in ROLE_PAGES.items():
            print(f"角色 {role}:")
            await login_as(page, role)
            for i, key in enumerate(keys):
                await goto_nav(page, key)
                await shot(page, f"{role}_{i+1}_{key}")
            # 智能助手面板（admin 问风险，parent 问孩子健康 → 展示新意图）
            if role in ("admin", "parent"):
                await page.click(".chat-fab")
                await page.fill("#chat-input",
                                "现在有什么风险？" if role == "admin" else "孩子健康档案怎么样？")
                await page.press("#chat-input", "Enter")
                await page.wait_for_timeout(1200)
                await shot(page, f"{role}_chat")
                await page.click(".chat-fab")
            await page.goto(BASE)  # 退出（reload 即回登录页）

        # 3. 应急状态对比一：放学高峰暴雨
        print("注入放学高峰暴雨场景，截应急状态:")
        await page.request.post(BASE + "/api/scenario/dismissal_rainstorm")
        await page.wait_for_timeout(800)

        await login_as(page, "admin")
        await goto_nav(page, "dashboard")
        # 展开第一条风险推理链
        try:
            await page.click("#dz-hz .list-item", timeout=3000)
            await page.wait_for_timeout(400)
        except Exception:
            pass
        await shot(page, "emergency_1_admin_dashboard")

        await page.goto(BASE)
        await login_as(page, "parent")
        await goto_nav(page, "inbox")
        await shot(page, "emergency_2_parent_inbox")
        await goto_nav(page, "travel")
        await shot(page, "emergency_3_parent_travel")

        # 4. 应急状态对比二：缺勤聚集（平时线数据驱动急时线预警）
        print("注入缺勤聚集场景:")
        await page.request.post(BASE + "/api/scenario/illness_cluster")
        await page.wait_for_timeout(800)
        await page.goto(BASE)
        await login_as(page, "teacher")
        await goto_nav(page, "leaveadmin")
        await shot(page, "emergency_4_teacher_illness_watch")

        # 5. 复位
        await page.request.post(BASE + "/api/brain/plan/reset")
        # 把注入产生的活跃风险推进到解除，保持环境干净
        hazards = await (await page.request.get(BASE + "/api/brain/hazards")).json()
        for hz in hazards:
            await page.request.post(BASE + f"/api/brain/hazards/{hz['id']}/advance")
            await page.request.post(BASE + f"/api/brain/hazards/{hz['id']}/advance")

        await browser.close()
        print(f"\n全部完成，输出目录：{OUT}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
