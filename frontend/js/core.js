/* ============================================================
   红门哨兵 v5 · 核心层：会话 / 导航 / 通用 UI 工厂 / 图表 / 对话
   组件样式来自 TDesign（本地 vendor），图标 Remix Icon，图表 ECharts
   v5 增强：骨架屏 / 粒子背景 / 数字动画 / 过渡动效 / 新增 UI 工厂
   ============================================================ */
const API = "";
let SESSION = null;
let CHILD = null;   // 家长登录后加载的孩子档案（一人一档不一人一号）

/* ---------------- 角色导航（4账号，无学生账号）----------------
   admin：资产台账归口校长（安全第一责任人），教师端不出现
   parent：孩子空间内嵌 → 健康/体测/成绩/选修课/请假/用餐全在家长账号下
   community：资源方只审批预约、处置工单，不发起预约 */
const ROLE_NAV = {
  admin: [["dashboard", "指挥大屏"], ["matrix", "预案矩阵"], ["workbench", "工单管理"], ["assets", "资产管理"], ["inspections", "年检公示"], ["spaces", "共享空间"]],
  teacher: [["inbox", "通知中心"], ["leaveadmin", "请假·缺勤"], ["spaces", "共享空间"], ["venues", "场馆点评"], ["inspections", "安全公示"], ["report", "随手拍"]],
  parent: [["child", "孩子空间"], ["courses", "选修课"], ["leave", "请假"], ["meals", "用餐日历"], ["inbox", "通知中心"], ["travel", "安全出行"], ["canteen", "食安公示"], ["report", "随手拍"]],
  community: [["workbench", "工单处置台"], ["hazards", "风险事件"], ["approvals", "预约审批"]],
};
const NAV_ICON = {
  dashboard: "ri-dashboard-3-line", matrix: "ri-list-settings-line", workbench: "ri-todo-line",
  assets: "ri-archive-drawer-line", inspections: "ri-shield-check-line", spaces: "ri-building-2-line",
  inbox: "ri-notification-3-line", leaveadmin: "ri-calendar-check-line", venues: "ri-star-smile-line",
  report: "ri-camera-line", child: "ri-user-heart-line", courses: "ri-book-open-line",
  leave: "ri-calendar-event-line", meals: "ri-restaurant-line", travel: "ri-walk-line",
  canteen: "ri-restaurant-2-line", hazards: "ri-alarm-warning-line", approvals: "ri-checkbox-multiple-line",
};
const CHAT_HINT = {
  parent: "您好！可以问我：孩子健康档案？选修课推荐？怎么请假？这个月饭费？现在有风险吗？",
  teacher: "您好！可以问我：当前预案？班里请假情况？预约场地？食堂留样？",
  community: "您好！可以问我：现在有什么风险？工单进度？",
  admin: "您好！可以问我：现在有什么风险？当前预案？食安指数？资产状况？",
};

/* ---------------- 通用 ---------------- */
async function api(path, opt) {
  const r = await fetch(API + path, opt);
  if (!r.ok) { let d; try { d = (await r.json()).detail } catch (e) { d = r.statusText } throw new Error(d) }
  return r.json();
}
function h(html) { const d = document.createElement("div"); d.innerHTML = html; return d }
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])) }
function fmt(t) { return t ? new Date(t).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—" }
const SEV = ["", "提示", "一般", "严重", "紧急"], SEVT = ["", "default", "primary", "warning", "danger"];
const HZL = { waterlogging: "积水内涝", typhoon_wind: "大风/台风", earthquake: "地震", food_safety: "食堂食安", air_quality: "教室空气", gate_congestion: "校门拥堵", illegal_parking: "违停", fire_channel_blocked: "消防通道占用", noise: "噪音", illness_cluster: "缺勤聚集(症状监测)", stair_crowding: "楼梯间拥挤" };
const HZI = { waterlogging: "ri-flood-line", typhoon_wind: "ri-windy-line", earthquake: "ri-earthquake-line", food_safety: "ri-restaurant-2-line", air_quality: "ri-haze-2-line", gate_congestion: "ri-group-line", illegal_parking: "ri-car-line", fire_channel_blocked: "ri-fire-line", noise: "ri-sound-module-line", illness_cluster: "ri-virus-line", stair_crowding: "ri-run-line" };
const STL = { reported: "已上报", dispatched: "已派单", processing: "处理中", resolved: "已解决", closed: "已归档" };
const CATL = { traffic: "交通", vendor: "游商", fire_hazard: "消防", environment: "环境", facility: "设施", food: "食安", air: "空气", flood: "积水", other: "其他" };
const BKL = { pending: "待审批", confirmed: "已批准", cancelled: "已取消/驳回", completed: "已完成" };
const WD = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const LVT = { sick: "病假", personal: "事假" };
function curMonth() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}` }
function isDark() { return document.body.classList.contains("dark") }

/* ==================== v5 新增：粒子背景动画 ==================== */
/* 粒子系统：在登录页绘制缓慢移动的粒子连线效果 */
let _particlesRAF = null;
let _particlesCtx = null;
let _particles = [];

function initParticles() {
  const canvas = document.createElement("canvas");
  canvas.id = "particles";
  canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0";
  const loginView = document.getElementById("login-view");
  if (loginView) {
    loginView.style.position = "relative";
    loginView.style.overflow = "hidden";
    loginView.insertBefore(canvas, loginView.firstChild);
  }
  const ctx = canvas.getContext("2d");
  _particlesCtx = ctx;
  /* 初始化50个粒子 */
  _particles = [];
  function resize() {
    canvas.width = loginView ? loginView.offsetWidth : window.innerWidth;
    canvas.height = loginView ? loginView.offsetHeight : window.innerHeight;
  }
  resize();
  window.addEventListener("resize", resize);
  for (let i = 0; i < 50; i++) {
    _particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      r: Math.random() * 2 + 1,
      alpha: Math.random() * 0.4 + 0.1
    });
  }
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    /* 绘制连线 */
    for (let i = 0; i < _particles.length; i++) {
      for (let j = i + 1; j < _particles.length; j++) {
        const dx = _particles[i].x - _particles[j].x;
        const dy = _particles[i].y - _particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          const alpha = (1 - dist / 150) * 0.15;
          ctx.beginPath();
          ctx.strokeStyle = `rgba(40, 209, 232, ${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.moveTo(_particles[i].x, _particles[i].y);
          ctx.lineTo(_particles[j].x, _particles[j].y);
          ctx.stroke();
        }
      }
    }
    /* 绘制粒子 */
    _particles.forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(0.5, p.r), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(40, 209, 232, ${p.alpha})`;
      ctx.fill();
      /* 移动粒子 */
      p.x += p.vx;
      p.y += p.vy;
      /* 边界回弹 */
      if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
    });
    _particlesRAF = requestAnimationFrame(draw);
  }
  draw();
}

/* 停止粒子动画（登录成功后调用） */
function stopParticles() {
  if (_particlesRAF) {
    cancelAnimationFrame(_particlesRAF);
    _particlesRAF = null;
  }
  const canvas = document.getElementById("particles");
  if (canvas) canvas.remove();
  _particles = [];
  _particlesCtx = null;
}

/* ==================== v5 新增：数字滚动动画 ==================== */
/* 从 0 滚动到目标值，easeOutExpo 缓动 */
function animateNumber(el, target, duration) {
  duration = duration || 800;
  /* 提取目标数值（支持带标签的HTML，取纯数字部分） */
  const targetStr = String(target);
  /* 如果包含 < 标签HTML，直接设置，不做动画 */
  if (targetStr.includes("<")) {
    if (el) el.innerHTML = targetStr;
    return;
  }
  const targetNum = parseFloat(targetStr);
  if (isNaN(targetNum)) {
    if (el) el.textContent = targetStr;
    return;
  }
  const isDecimal = targetStr.includes(".");
  const decimals = isDecimal ? (targetStr.split(".")[1] || "").length : 0;
  const start = performance.now();
  /* easeOutExpo 缓动函数 */
  function easeOutExpo(t) {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }
  function tick(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const easedProgress = easeOutExpo(progress);
    const current = easedProgress * targetNum;
    el.textContent = current.toFixed(decimals);
    if (progress < 1) {
      requestAnimationFrame(tick);
    } else {
      el.textContent = targetStr;
    }
  }
  requestAnimationFrame(tick);
}

/* ==================== v5 新增：内联样式注入（用于过渡动画） ==================== */
/* 注入 core.js 所需的动画关键帧和过渡类，不依赖外部 CSS */
function _injectCoreStyles() {
  if (document.getElementById("_core-v5-styles")) return;
  const style = document.createElement("style");
  style.id = "_core-v5-styles";
  style.textContent = `
    /* 登录加载骨架屏 */
    .login-skl { border-radius:12px; height:56px; margin-bottom:10px;
      background:linear-gradient(100deg,rgba(255,255,255,.04) 40%,rgba(122,168,255,.1) 50%,rgba(255,255,255,.04) 60%);
      background-size:200% 100%; animation:shimmer 1.2s infinite linear;
      border:1px solid rgba(122,168,255,.12); }
    /* 账号卡片 fadein 入场 */
    .acct-fadein { opacity:0; transform:translateY(8px); animation:acctFadeIn .35s ease forwards; }
    @keyframes acctFadeIn { to { opacity:1; transform:none; } }
    /* 全屏 loading 遮罩 */
    .login-loading { position:fixed; inset:0; z-index:200; display:flex; flex-direction:column;
      align-items:center; justify-content:center; gap:16px;
      background:radial-gradient(1200px 700px at 20% 0%,#14498f 0%,#0d2a52 45%,#081226 100%);
      color:#eaf2ff; transition:opacity .4s ease; }
    .login-loading.fade-out { opacity:0; pointer-events:none; }
    .login-loading .spinner { width:36px; height:36px; border:3px solid rgba(40,209,232,.2);
      border-top-color:#28d1e8; border-radius:50%; animation:spin .8s linear infinite; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .login-loading .load-text { font-size:14px; color:#9db8dd; letter-spacing:1px; }
    /* 页面切换过渡 */
    #main.page-fade-out { opacity:0; transform:translateY(-10px); transition:all .2s ease; }
    #main.page-fade-in { opacity:0; transform:translateX(20px); animation:pageSlideIn .3s ease forwards; }
    @keyframes pageSlideIn { to { opacity:1; transform:none; } }
    /* 导航按钮入场 */
    .nav-fadein { opacity:0; animation:navFadeIn .25s ease forwards; }
    @keyframes navFadeIn { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:none; } }
    /* 面板进入动画 */
    .panel-enter { animation:panelEnter .4s cubic-bezier(.23,1,.32,1); }
    @keyframes panelEnter { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:none; } }
    /* 空态图标微浮动 */
    .empty i { animation:emptyFloat 2.5s ease-in-out infinite; }
    @keyframes emptyFloat { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-3px); } }
    /* 星星逐个亮起 */
    .star-animate { opacity:0; animation:starLightUp .3s ease forwards; }
    @keyframes starLightUp { from { opacity:0; transform:scale(0.6); } to { opacity:1; transform:scale(1); } }
    /* toast 入场退场动画 */
    .toast { animation:toastSlideDown .25s ease, toastFadeOut .3s ease 2.8s forwards; }
    @keyframes toastSlideDown { from { opacity:0; transform:translateX(-50%) translateY(-12px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }
    @keyframes toastFadeOut { to { opacity:0; transform:translateX(-50%) translateY(-8px); } }
    /* 聊天面板弹出动画 */
    .chat-panel.chat-enter { animation:chatPopIn .3s cubic-bezier(.23,1,.32,1); }
    @keyframes chatPopIn { from { opacity:0; transform:scale(.92) translateY(10px); } to { opacity:1; transform:none; } }
    /* 打字指示器 */
    .typing-indicator { display:flex; gap:4px; padding:10px 14px; align-items:center;
      background:var(--bg-page); border-radius:0 10px 10px 0; border-left:3px solid var(--brand);
      align-self:flex-start; }
    .typing-indicator .dot { width:6px; height:6px; border-radius:50%;
      background:var(--ink-3); animation:typingBounce .6s ease infinite; }
    .typing-indicator .dot:nth-child(2) { animation-delay:.15s; }
    .typing-indicator .dot:nth-child(3) { animation-delay:.3s; }
    @keyframes typingBounce { 0%,100% { transform:translateY(0); opacity:.4; } 50% { transform:translateY(-4px); opacity:1; } }
    /* 消息时间戳 */
    .msg-time { font-size:10px; color:var(--ink-3); margin-top:3px; opacity:.7; }
    .msg.me .msg-time { text-align:right; color:rgba(255,255,255,.6); }
    /* 导航 active 底部横线过渡 */
    .app-nav button::after { content:""; position:absolute; bottom:-1px; left:50%; width:0; height:2.5px;
      background:var(--brand); border-radius:2px; transition:width .25s ease, left .25s ease; }
    .app-nav button { position:relative; }
    .app-nav button.active::after { width:calc(100% - 28px); left:14px; }
    /* 应急横幅 */
    .emergency-banner { padding:8px 16px; text-align:center; font-size:13px; color:#fff;
      background:linear-gradient(90deg,#d54941,#e37318,#d54941); background-size:200% 100%;
      animation:emergencyBannerGradient 3s ease infinite; position:relative; z-index:48;
      box-shadow:0 2px 12px rgba(213,73,65,.3); }
    @keyframes emergencyBannerGradient { 0%,100%{background-position:0% 50%;} 50%{background-position:100% 50%;} }
    .emergency-banner i { margin-right:6px; }
    /* 应急模式 header 闪烁边框 */
    .app-header.emergency-border { animation:headerBorderPulse 1.5s ease infinite; }
    @keyframes headerBorderPulse { 0%,100%{box-shadow:0 0 0 0 rgba(213,73,65,0);} 50%{box-shadow:0 0 0 2px rgba(213,73,65,.5), 0 2px 16px rgba(213,73,65,.2);} }
    /* 骨架屏计数动画 */
    .skl-count { position:absolute; bottom:8px; right:12px; font-size:11px; color:var(--ink-3);
      animation:sklCountPulse 1s ease infinite; }
    @keyframes sklCountPulse { 0%,100%{opacity:.4;} 50%{opacity:.9;} }
    .skl { position:relative; }
    /* btn ripple 效果（CSS-only via ::after） */
    .btn-ripple { position:relative; overflow:hidden; }
    .btn-ripple::after { content:""; position:absolute; inset:0;
      background:radial-gradient(circle at var(--ripple-x,50%) var(--ripple-y,50%), rgba(255,255,255,.25) 0%, transparent 60%);
      opacity:0; transition:opacity .4s ease; pointer-events:none; }
    .btn-ripple:active::after { opacity:1; transition:opacity 0s; }
    /* hero-stat 额外样式 */
    .hero-stat { border-radius:var(--r-lg); background:var(--bg-card); border:1px solid var(--line);
      box-shadow:var(--shadow-1); transition:transform .2s ease, box-shadow .2s ease; }
    .hero-stat:hover { transform:translateY(-2px); box-shadow:var(--shadow-2); }
    .hero-stat .hero-icon { font-size:28px; margin-bottom:8px; }
    /* 进度条组件 */
    .progress-bar-wrap { margin:4px 0; }
    .progress-bar-label { display:flex; justify-content:space-between; align-items:center;
      font-size:var(--fs-xs); color:var(--ink-2); margin-bottom:4px; }
    .progress-bar-track { height:8px; border-radius:4px; background:var(--line); overflow:hidden; }
    .progress-bar-fill { height:100%; border-radius:4px; transition:width .8s cubic-bezier(.23,1,.32,1); }
    /* 应用 view crossfade */
    #app-view.crossfade-enter { animation:crossfadeIn .5s ease; }
    @keyframes crossfadeIn { from { opacity:0; } to { opacity:1; } }
  `;
  document.head.appendChild(style);
}
/* 自动注入样式 */
_injectCoreStyles();

/* ---------------- UI 工厂：统一 TDesign 视觉件（v5 增强版） ---------------- */
function tag(text, theme, icon) {   // theme: primary/success/warning/danger/default/purple
  /* v5: pill 圆角 + icon 文字间距微调 */
  return `<span class="t-tag t-tag--${theme || "default"} t-tag--light" style="border-radius:999px">${icon ? `<i class="${icon}" style="margin-right:3px"></i>` : ""}${esc(text)}</span>`;
}
function btn(label, onclick, opt) { // opt: {theme:"primary|danger|default", variant:"base|outline|text", icon, size}
  const o = opt || {};
  /* v5: 加 ripple 类 + hover 过渡动效 */
  const btnStyle = `transition:transform .15s ease,box-shadow .15s ease;cursor:pointer;`;
  const hoverCode = `onmouseenter="this.style.transform='scale(1.02)'" onmouseleave="this.style.transform='scale(1)'"`;
  return `<button class="t-button t-button--theme-${o.theme || "primary"} t-button--variant-${o.variant || "base"} t-size-${o.size || "s"} btn-ripple" style="${btnStyle}" onclick="${onclick}" ${hoverCode}>` +
    `${o.icon ? `<i class="${o.icon}" style="margin-right:4px"></i>` : ""}<span class="t-button__text">${label}</span></button>`;
}
function panel(icon, title, desc, body, extra) {
  /* v5: 增加面板进入动画类名 */
  return `<div class="panel panel-enter"><div class="panel-hd"><i class="${icon}"></i><h3>${title}</h3>` +
    `${desc ? `<span class="panel-desc">${desc}</span>` : ""}${extra ? `<span class="extra">${extra}</span>` : ""}</div>` +
    `<div class="panel-bd">${body}</div></div>`;
}
function kpi(icon, num, label, mood) {  // mood: good/warn/bad/""
  /* v5: 先显示 0，通过 data-target 实现数字动画 */
  const targetVal = String(num);
  return `<div class="kpi ${mood || ""}"><div class="ic"><i class="${icon}"></i></div>` +
    `<div><div class="num" data-countup="${esc(targetVal)}">0</div><div class="lbl">${label}</div></div></div>`;
}
function empty(icon, text) {
  /* v5: 图标加微浮动（通过注入的 CSS 动画类） */
  return `<div class="empty"><i class="${icon || "ri-inbox-line"}"></i><p>${esc(text || "暂无数据")}</p></div>`;
}
function rateStars(n) {
  let s = "";
  /* v5: 星星加逐个亮起的延迟动画 */
  for (let i = 1; i <= 5; i++) {
    const filled = i <= Math.round(n);
    const delay = i * 80;
    s += `<i class="ri-star-fill star-animate" style="color:${filled ? "#e8a52e" : "var(--line)"};font-size:14px;animation-delay:${delay}ms;opacity:${filled ? "1" : "0.4"}"></i>`;
  }
  return `<span style="letter-spacing:1px">${s}</span>`;
}
function toast(text, kind) {
  document.querySelectorAll(".toast").forEach(t => t.remove());
  const ic = kind === "error" ? "ri-close-circle-line" : "ri-checkbox-circle-line";
  const t = h(`<div class="toast ${kind || "success"}"><i class="${ic}"></i><span>${esc(text)}</span></div>`).firstChild;
  document.body.appendChild(t);
  /* v5: 退场由 CSS 动画处理（2.8s 后 fadeOut），3.2s 后移除 DOM */
  setTimeout(() => t.remove(), 3200);
}

/* ---------------- v5 新增 UI 工厂函数 ---------------- */

/* 大数据展示卡（.hero-stat） */
function heroStat(icon, num, label, desc, mood) {
  return `<div class="hero-stat">
    <div class="hero-icon" style="color:var(--brand)">${icon ? `<i class="${icon}"></i>` : ""}</div>
    <div class="hero-num" data-countup="${esc(String(num))}">0</div>
    <div class="hero-lbl">${label || ""}</div>
    ${desc ? `<div class="hero-sub">${desc}</div>` : ""}</div>`;
}

/* 紧凑指标卡（.stat-card） */
function statCard(icon, num, label, desc, mood) {
  return `<div class="stat-card">
    <div class="stat-val" data-countup="${esc(String(num))}" style="color:${mood === "good" ? "#2ba471" : mood === "bad" ? "#d54941" : mood === "warn" ? "#e37318" : "var(--ink)"}">0</div>
    <div class="stat-lbl">${label || ""}</div>
    ${desc ? `<div class="stat-lbl" style="color:var(--ink-3);font-size:11px">${desc}</div>` : ""}</div>`;
}

/* 渐变分割线 */
function divider(text) {
  return `<div class="divider">${esc(text || "")}</div>`;
}

/* 状态点 */
function statusDot(status, text) {
  return `<span class="status-dot ${status || ""}">${esc(text || "")}</span>`;
}

/* 指标行，items=[{icon,num,label}] */
function metricRow(items) {
  return `<div class="metric-row">${(items || []).map(it =>
    `<div class="metric-item">
      ${it.icon ? `<i class="${it.icon}" style="font-size:14px;color:var(--brand);margin-bottom:2px"></i>` : ""}
      <div class="metric-val" data-countup="${esc(String(it.num || 0))}">0</div>
      <div class="metric-lbl">${esc(it.label || "")}</div>
    </div>`
  ).join("")}</div>`;
}

/* 数字徽标 */
function badge(count, type) {
  return `<span class="badge ${type || ""}">${count}</span>`;
}

/* 进度条 */
function progressBar(pct, color, label) {
  const p = Math.min(100, Math.max(0, Number(pct) || 0));
  const c = color || "var(--brand)";
  return `<div class="progress-bar-wrap">
    <div class="progress-bar-label"><span>${esc(label || "")}</span><span>${p}%</span></div>
    <div class="progress-bar-track"><div class="progress-bar-fill" style="width:${p}%;background:${c}"></div></div></div>`;
}

/* ---------------- ECharts：挂载队列 + 主题基色 ---------------- */
const _mountQueue = [];
function mount(fn) { _mountQueue.push(fn) }
function flushMount() {
  /* v5: flushMount 时触发所有 data-countup 数字动画 */
  document.querySelectorAll("[data-countup]").forEach(el => {
    const target = el.getAttribute("data-countup");
    if (target) animateNumber(el, target, 800);
  });
  /* 执行挂载队列 */
  while (_mountQueue.length) { try { _mountQueue.shift()() } catch (e) { console.warn(e) } }
}
function chart(el, option, height) {
  el.style.height = (height || 220) + "px";
  const c = echarts.init(el, null, { renderer: "canvas" });
  const dk = isDark();
  option.textStyle = { fontFamily: "PingFang SC, Microsoft YaHei, sans-serif", color: dk ? "#8fa9d6" : "#5f6b82" };
  if (option.xAxis) [].concat(option.xAxis).forEach(a => { a.axisLine = a.axisLine || { lineStyle: { color: dk ? "#22406e" : "#dcdcdc" } }; a.axisLabel = Object.assign({ color: dk ? "#8fa9d6" : "#7d8ba5", fontSize: 11 }, a.axisLabel) });
  if (option.yAxis) [].concat(option.yAxis).forEach(a => { a.splitLine = a.splitLine || { lineStyle: { color: dk ? "#16294f" : "#eef1f6" } }; a.axisLabel = Object.assign({ color: dk ? "#8fa9d6" : "#7d8ba5", fontSize: 11 }, a.axisLabel) });
  /* v5: 支持渐变色 series itemStyle gradient 对象 */
  if (option.series) [].concat(option.series).forEach(s => {
    /* 如果 itemStyle.color 是 {gradient} 对象，转换为 ECharts 渐变 */
    if (s.itemStyle && s.itemStyle.color && typeof s.itemStyle.color === "object" && s.itemStyle.color.gradient) {
      const g = s.itemStyle.color.gradient;
      const grad = new echarts.graphic.LinearGradient(g.direction || 0, g.x1 || 0, g.y1 || 0, g.x2 || 0, g.y2 || 1,
        (g.stops || []).map(st => ({ offset: st.offset || 0, color: st.color })));
      s.itemStyle.color = grad;
    }
    /* v5: 支持 animationDelay 回调 */
    if (s.animationDelay && typeof s.animationDelay === "function") {
      option.animationDelay = s.animationDelay;
      delete s.animationDelay;
    }
  });
  /* v5: 如果 option 中传入了 _theme，应用主题配置 */
  if (option._theme) {
    const theme = option._theme;
    if (theme.tooltip) option.tooltip = Object.assign(option.tooltip || {}, theme.tooltip);
    if (theme.legend) option.legend = Object.assign(option.legend || {}, theme.legend);
    delete option._theme;
  }
  c.setOption(option);
  window.addEventListener("resize", () => c.resize());
  return c;
}

/* v5: chartTheme() 返回深色/浅色完整主题对象 */
function chartTheme(mode) {
  const dk = mode === "dark" || isDark();
  return dk ? {
    tooltip: { backgroundColor: "rgba(14,28,60,0.9)", borderColor: "rgba(40,209,232,0.2)", textStyle: { color: "#dbe7ff", fontSize: 12 } },
    legend: { textStyle: { color: "#8fa9d6", fontSize: 11 } }
  } : {
    tooltip: { backgroundColor: "#fff", borderColor: "#dcdcdc", textStyle: { color: "rgba(0,0,0,.9)", fontSize: 12 } },
    legend: { textStyle: { color: "#5f6b82", fontSize: 11 } }
  };
}

const C_BLUE = "#0052d9", C_CYAN = "#0fa8bd", C_ORANGE = "#e37318", C_RED = "#d54941", C_GREEN = "#2ba471";

/* ---------------- 登录：点选身份进入，不展示口令（v5 增强版） ---------------- */
async function initLogin() {
  /* 启动粒子背景 */
  initParticles();
  const p = document.getElementById("quick-panel");
  /* v5: 先显示骨架屏（3个闪烁卡片） */
  p.innerHTML = `<div class="login-skl"></div><div class="login-skl"></div><div class="login-skl"></div>`;
  try {
    const list = await api("/api/auth/accounts");
    const meta = {
      admin: ["ri-government-line", "linear-gradient(135deg,#d54941,#e37318)"],
      teacher: ["ri-user-star-line", "linear-gradient(135deg,#0052d9,#4d9fff)"],
      parent: ["ri-parent-line", "linear-gradient(135deg,#0fa8bd,#2ba471)"],
      community: ["ri-community-line", "linear-gradient(135deg,#7b46d1,#a678f0)"],
    };
    /* v5: 清空骨架屏，逐个 fadein 账号卡片 */
    p.innerHTML = "";
    list.forEach((a, idx) => {
      const [ic, bg] = meta[a.role] || ["ri-user-line", "#1a66cc"];
      const acctEl = h(`<div class="acct acct-fadein" onclick="quickLogin('${a.username}')" style="animation-delay:${idx * 150}ms">
        <div class="av" style="background:${bg}"><i class="${ic}"></i></div>
        <div class="nm"><b>${esc(a.name)}</b><div class="meta">${esc(a.role_label || a.role)}</div></div>
        <i class="ri-arrow-right-s-line go"></i></div>`).firstChild;
      p.appendChild(acctEl);
    });
  } catch (e) { document.getElementById("li-err").textContent = "服务未就绪：" + e.message }
}
async function quickLogin(u) {
  /* v5: 显示全屏 loading 动画（旋转 + 提示文字） */
  const loading = document.createElement("div");
  loading.className = "login-loading";
  loading.innerHTML = `<div class="spinner"></div><div class="load-text">正在进入系统...</div>`;
  document.body.appendChild(loading);
  try {
    SESSION = await api("/api/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: "123456" })
    });
    /* 停止粒子动画 */
    stopParticles();
    /* v5: crossfade 过渡：先让 loading 淡出 */
    loading.classList.add("fade-out");
    /* 同时准备 app-view */
    document.getElementById("login-view").style.display = "none";
    const av = document.getElementById("app-view"); av.classList.remove("hidden");
    av.classList.add("crossfade-enter");
    av.style.display = "";
    /* 等待 loading 淡出动画完成后再移除 */
    setTimeout(() => {
      loading.remove();
      av.classList.remove("crossfade-enter");
    }, 400);
    /* 校长端 = 城运中心深色大屏：body.dark（自有令牌） + theme-mode（TDesign 暗色变量） */
    const dark = SESSION.role === "admin";
    document.body.classList.toggle("dark", dark);
    document.documentElement.setAttribute("theme-mode", dark ? "dark" : "");
    const roleLabel = { admin: "校长·安全第一责任人", parent: "家长", teacher: "班主任", community: "社区·红门管家" }[SESSION.role] || SESSION.role;
    document.getElementById("who").innerHTML = `<i class="ri-user-follow-line"></i> ${esc(SESSION.name)} · ${roleLabel}`;
    document.getElementById("chat-msgs").innerHTML = `<div class="msg bot">${esc(CHAT_HINT[SESSION.role] || CHAT_HINT.parent)}</div>`;
    if (SESSION.role === "parent") {
      const kids = await api(`/api/children/by-parent/${SESSION.user_id}`);
      CHILD = kids[0] || null;
    }
    buildNav(); refreshMode(); setInterval(refreshMode, 8000);
  } catch (e) {
    loading.remove();
    document.getElementById("li-err").textContent = e.message;
  }
}
function logout() { document.body.classList.remove("dark"); document.documentElement.removeAttribute("theme-mode"); location.reload() }
function buildNav() {
  const nav = document.getElementById("nav"); nav.innerHTML = "";
  const items = ROLE_NAV[SESSION.role] || ROLE_NAV.parent;
  items.forEach(([k, label], i) => {
    const b = document.createElement("button");
    b.innerHTML = `<i class="${NAV_ICON[k] || "ri-apps-line"}"></i>${label}`;
    b.dataset.page = k; b.onclick = () => go(k);
    /* v5: 导航按钮逐个 fadein 出现 */
    b.classList.add("nav-fadein");
    b.style.animationDelay = `${i * 100}ms`;
    nav.appendChild(b);
    /* v5: 第一个自动激活动画从左到右滑入（已通过 nav-fadein 实现） */
    if (i === 0) go(k);
  });
}
function go(page) {
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  const m = document.getElementById("main");
  /* v5: 当前内容 fadeOut（opacity 0, translateY -10px） */
  m.classList.add("page-fade-out");
  /* v5: 骨架屏加计数动画（模拟数据加载感） */
  setTimeout(() => {
    m.classList.remove("page-fade-out");
    m.innerHTML = `<div class="skl" style="height:96px"><span class="skl-count">加载中 0%</span></div><div class="skl" style="height:220px"><span class="skl-count">加载中 0%</span></div><div class="skl" style="height:160px"><span class="skl-count">加载中 0%</span></div>`;
    /* 骨架屏计数动画：模拟加载进度 */
    const counters = m.querySelectorAll(".skl-count");
    let progress = 0;
    const countInterval = setInterval(() => {
      progress = Math.min(progress + Math.floor(Math.random() * 20 + 5), 95);
      counters.forEach(c => { c.textContent = `加载中 ${progress}%`; });
    }, 200);
    m.classList.add("page-fade-in");
    PAGES[page]().then(el => {
      clearInterval(countInterval);
      m.classList.remove("page-fade-in");
      m.innerHTML = "";
      m.appendChild(el);
      flushMount();
    }).catch(e => {
      clearInterval(countInterval);
      m.classList.remove("page-fade-in");
      m.innerHTML = `<div class="page-err"><i class="ri-alert-line"></i> 加载失败：${esc(e.message)}</div>`;
    });
  }, 200);
}
async function refreshMode() {
  try {
    const cur = await api("/api/brain/plan/current");
    const pill = document.getElementById("mode-pill");
    let theme = "success", icon = "ri-checkbox-circle-line", blink = "";
    if (cur.mode === "staggered") { theme = "warning"; icon = "ri-timer-flash-line" }
    if (["indoor", "home_study", "evacuate"].includes(cur.mode)) { theme = "danger"; icon = "ri-alarm-warning-line"; blink = " blink" }
    pill.className = `t-tag t-tag--${theme} t-tag--dark${blink}`;
    pill.innerHTML = `<i class="${icon}"></i> ${esc(cur.mode_label)}`;

    /* v5: 应急模式视觉增强 */
    const header = document.querySelector(".app-header");
    const isEmergency = ["indoor", "home_study", "evacuate"].includes(cur.mode);
    /* 应急闪烁边框 */
    header.classList.toggle("emergency-border", isEmergency);
    /* 应急横幅 */
    let banner = document.querySelector(".emergency-banner");
    if (isEmergency) {
      if (!banner) {
        banner = document.createElement("div");
        banner.className = "emergency-banner";
        document.querySelector(".app-nav").after(banner);
      }
      banner.innerHTML = `<i class="ri-alarm-warning-line"></i> 应急模式：${esc(cur.mode_label)} —— 请关注最新通知，按预案行动`;
      banner.style.display = "";
    } else if (banner) {
      banner.style.display = "none";
    }
  } catch (e) { }
}

/* ---------------- 对话（v5 增强版） ---------------- */
let _chatOpen = false;
function toggleChat() {
  const p = document.getElementById("chat-panel");
  if (!_chatOpen) {
    p.style.display = "";
    /* v5: 面板展开 slide + scale 动画 */
    p.classList.remove("chat-enter");
    void p.offsetWidth; /* 触发 reflow */
    p.classList.add("chat-enter");
    _chatOpen = true;
  } else {
    /* v5: 面板收起：先加淡出再隐藏 */
    p.style.opacity = "0";
    p.style.transform = "scale(.92) translateY(10px)";
    p.style.transition = "all .2s ease";
    setTimeout(() => {
      p.style.display = "none";
      p.style.opacity = ""; p.style.transform = ""; p.style.transition = "";
      p.classList.remove("chat-enter");
    }, 200);
    _chatOpen = false;
  }
}
async function sendChat() {
  const inp = document.getElementById("chat-input"), box = document.getElementById("chat-msgs");
  const text = inp.value.trim(); if (!text) return; inp.value = "";
  /* v5: 消息加时间戳 */
  const now = new Date();
  const timeStr = now.getHours().toString().padStart(2, "0") + ":" + now.getMinutes().toString().padStart(2, "0");
  box.appendChild(h(`<div class="msg me">${esc(text)}<div class="msg-time">${timeStr}</div></div>`).firstChild);
  box.scrollTop = box.scrollHeight;
  /* v5: 显示打字指示器（三个跳动的点） */
  const typing = document.createElement("div");
  typing.className = "typing-indicator";
  typing.innerHTML = `<div class="dot"></div><div class="dot"></div><div class="dot"></div>`;
  box.appendChild(typing);
  box.scrollTop = box.scrollHeight;
  try {
    const r = await api("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: SESSION.role, message: text })
    });
    /* v5: 1秒后移除打字指示器并显示回复 */
    setTimeout(() => {
      typing.remove();
      let extra = "";
      if (r.intent === "query_hazard" && Array.isArray(r.data))
        extra = r.data.length ? "<br>" + r.data.map(d => `· ${HZL[d.hazard_class] || d.hazard_class} @ ${esc(d.zone)}（${SEV[d.severity]}）`).join("<br>") : "<br>当前无活跃风险 ✓";
      if (r.intent === "query_plan" && r.data) extra = `<br>当前模式：<b>${esc(r.data.mode)}</b>${r.data.alert ? "（" + esc(r.data.alert) + "）" : ""}`;
      /* v5: bot 消息也加时间戳 */
      const replyTime = new Date();
      const replyTimeStr = replyTime.getHours().toString().padStart(2, "0") + ":" + replyTime.getMinutes().toString().padStart(2, "0");
      box.appendChild(h(`<div class="msg bot">${esc(r.reply)}${extra}<div class="msg-time">${replyTimeStr}</div></div>`).firstChild);
      box.scrollTop = box.scrollHeight;
      const jump = {
        query_hazard: "hazards", query_plan: "matrix", query_canteen: "canteen", query_asset: "assets",
        report_incident: "report", query_safety: "travel", find_resource: "spaces", book_resource: "spaces",
        query_health: "child", query_course: "courses", ask_leave: "leave", query_meal: "meals"
      }[r.intent];
      if (jump && (ROLE_NAV[SESSION.role] || []).some(([k]) => k === jump)) go(jump);
    }, 1000);
  } catch (e) {
    typing.remove();
    box.appendChild(h(`<div class="msg bot">出错了：${esc(e.message)}</div>`).firstChild);
    box.scrollTop = box.scrollHeight;
  }
}
