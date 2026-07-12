/* ============================================================
   红门哨兵 v5 · 页面层：18 个角色页面（视觉增强版）
   工厂增强：heroStat / statCard / metricRow / divider / statusDot / badge / progressBar
   ECharts 增强：渐变色 / animationDelay / chartTheme
   设计原则：打破同构 · 信息密度分层 · 每页签名时刻
   ============================================================ */
const PAGES = {
  dashboard: pgDashboard, matrix: pgMatrix, workbench: pgWorkbench, spaces: pgSpaces, inbox: pgInbox,
  travel: pgTravel, canteen: pgCanteen, report: pgReport, assets: pgAssets, hazards: pgHazards, approvals: pgApprovals,
  child: pgChild, courses: pgCourses, leave: pgLeave, meals: pgMeals, leaveadmin: pgLeaveAdmin,
  inspections: pgInspections, venues: pgVenues
};

/* ==================== 辅助工具：严重度色条 ==================== */
/* 根据 severity 级别返回左边框色值（越高越红） */
function sevBorder(severity) {
  const colors = ["", "var(--brand)", C_CYAN, C_ORANGE, C_RED];
  return colors[Number(severity)] || colors[1];
}

/* 来源对应的图标和色彩 */
const SRC_META = {
  citizen:  { icon: "ri-camera-line", color: "#7b46d1" },
  vision:   { icon: "ri-vidicon-line", color: C_CYAN },
  iot:      { icon: "ri-wifi-line", color: C_ORANGE },
  asset:    { icon: "ri-qr-scan-2-line", color: C_BLUE },
  scenario: { icon: "ri-film-line", color: "#e37318" },
};

/* ==================== 1. 指挥大屏（admin=校长） ==================== */
async function pgDashboard() {
  const [hazards, tele, stats, scens, cur, evac] = await Promise.all([
    api("/api/brain/hazards"), api("/api/perception/telemetry/latest"),
    api("/api/incidents/stats"), api("/api/scenario"), api("/api/brain/plan/current"),
    api("/api/brain/routes/evacuation")]);
  const anomaly = tele.filter(t => t.is_anomaly).length;
  const maxCost = Math.max(...evac.routes.map(r => r.cost_m), 1);
  const el = h(`<div>
    <div class="data-grid">
      ${heroStat("ri-alarm-warning-line", hazards.length, "活跃风险事件", "多模态融合确认", hazards.length ? "bad" : "good")}
      ${heroStat("ri-wifi-line", anomaly, "异常 IoT", `<span style="font-size:12px;color:var(--ink-3)">${anomaly}/${tele.length} 在网设备</span>`, anomaly ? "warn" : "good")}
      ${heroStat("ri-todo-line", stats.total, "累计工单", Object.entries(stats.by_source).map(([k, v]) => k + " " + v).join(" · ") || "—")}
      ${heroStat(cur.mode === "normal" ? "ri-checkbox-circle-line" : "ri-shield-flash-line", cur.mode_label, "校园运行模式", cur.plan ? btn("解除应急", "resetPlan()", { theme: "default", variant: "outline", icon: "ri-refresh-line" }) : "", cur.mode === "normal" ? "good" : "bad")}
    </div>
    <div class="grid g2">
      ${panel("ri-node-tree", "融合风险事件", "点击条目展开本体推理链",
        `<div id="dz-hz">${hazards.length ? "" : empty("ri-shield-check-line", "无活跃风险。所有信号均低于交叉印证阈值。")}</div>`)}
      ${panel("ri-film-line", "场景注入器", "一键回放典型事件驱动全链路",
        `<div id="dz-scen"></div><div class="timeline" id="dz-tl" style="display:none"></div>`)}
      ${panel("ri-broadcast-line", "IoT 遥测实时状态", "",
        `<table class="tbl"><tr><th>设备</th><th>读数</th><th>阈值</th><th>状态</th></tr>
        ${tele.map(t => `<tr><td>${esc(t.name)}<div class="muted">${t.device_id} @ ${esc(t.zone)}</div></td>
        <td><b>${t.value ?? "—"}</b> ${t.unit || ""}</td><td class="muted">${t.threshold_high ? "≤" + t.threshold_high : "—"}</td>
        <td>${t.is_anomaly ? statusDot("error", "越限") : statusDot("online", "正常")}</td></tr>`).join("")}</table>`)}
      ${panel("ri-route-line", "实时疏散路线", "Dijkstra · 风险加权",
        `${evac.routes.map(r => `<div class="list-item"><b>${esc(r.from)}</b> <i class="ri-arrow-right-s-line" style="color:var(--ink-3)"></i> ${r.path.slice(1).map(esc).join(" → ")}
        ${progressBar(Math.round(r.cost_m / maxCost * 100), r.cost_m > maxCost * 0.7 ? C_RED : (r.cost_m > maxCost * 0.4 ? C_ORANGE : C_GREEN), `代价 ${r.cost_m}m`)}
        </div>`).join("")}
        <div class="muted" style="margin-top:8px">风险区域：${Object.keys(evac.hazard_zones).length ? Object.entries(evac.hazard_zones).map(([z, s]) => `${esc(z)}(${SEV[s]})`).join("、") : "无 — 全部走最短路"}</div>`)}
    </div></div>`);
  const hzBox = el.querySelector("#dz-hz");
  hazards.forEach(hz => {
    const borderColor = sevBorder(hz.severity);
    const item = h(`<div class="list-item" style="cursor:pointer;border-left-color:${borderColor};border-left-width:4px">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      ${tag(SEV[hz.severity], SEVT[hz.severity])} <i class="${HZI[hz.hazard_class] || "ri-alert-line"}" style="color:var(--brand)"></i>
      <b>${HZL[hz.hazard_class] || hz.hazard_class}</b>
      <span class="muted">@ ${esc(hz.zone)} · ${fmt(hz.created_at)} · ${hz.sources.length}路信号</span>
      <span style="margin-left:auto">${btn(hz.status === "active" ? "开始处置" : "标记解除", `event.stopPropagation();advanceHazard(${hz.id})`, { theme: "default", variant: "outline" })}</span></div>
      <pre class="chain" style="display:none">${esc(hz.inference)}</pre></div>`).firstChild;
    item.onclick = () => { const p = item.querySelector("pre"); p.style.display = p.style.display === "none" ? "" : "none" };
    hzBox.appendChild(item);
  });
  const scenBox = el.querySelector("#dz-scen");
  /* 场景注入器按钮：每个场景不同色系 */
  const scenColors = ["#0052d9", "#0fa8bd", "#7b46d1", "#e37318", "#d54941", "#2ba471"];
  scens.forEach((s, i) => {
    const c = scenColors[i % scenColors.length];
    scenBox.appendChild(h(`<button class="scen-btn" onclick="runScenario('${s.name}')" style="border-left:3px solid ${c}">
    <b><i class="ri-play-circle-line" style="color:${c}"></i>${esc(s.label)}</b><div class="muted">${esc(s.desc)}</div></button>`).firstChild);
  });
  return el;
}
async function runScenario(name) {
  const tl = document.getElementById("dz-tl"); tl.style.display = ""; tl.innerHTML = `<i class="ri-loader-4-line spin"></i> 注入中…`;
  try {
    const r = await api("/api/scenario/" + name, { method: "POST" });
    tl.innerHTML = r.timeline.map(t => "▸ " + esc(t)).join("<br>"); refreshMode();
    setTimeout(() => go("dashboard"), 2600);
  } catch (e) { tl.textContent = "失败：" + e.message }
}
async function advanceHazard(id) { await api(`/api/brain/hazards/${id}/advance`, { method: "POST" }); go(document.querySelector("nav .active").dataset.page) }
async function resetPlan() { await api("/api/brain/plan/reset", { method: "POST" }); refreshMode(); go("dashboard") }

/* ==================== 2. 预案矩阵（admin） ==================== */
async function pgMatrix() {
  const rows = await api("/api/brain/plan/matrix");
  const LV = { blue: "蓝", yellow: "黄", orange: "橙", red: "红", warning: "预警" };
  const AT = { rainstorm: "暴雨", typhoon: "台风", earthquake: "地震", heat: "高温", air_pollution: "空气污染" };
  return h(`<div>
    ${divider("预警类型 × 级别 → 运行模式")}
    ${panel("ri-list-settings-line", "预警响应矩阵", "全量公开 · 每次切换留审计痕",
    `<div class="muted" style="margin-bottom:10px">数字化自北京市教委预警响应流程：预警类型×级别 → 运行模式 + 动作清单。标记「自动」的动作由智能体直接执行。</div>
    <table class="tbl"><tr><th>预警</th><th>运行模式</th><th>动作清单</th></tr>
    ${rows.map(p => `<tr style="transition:background .15s ease"><td><b>${AT[p.alert_type] || p.alert_type}·${LV[p.alert_level] || p.alert_level}</b></td>
    <td>${tag(p.mode_label, p.mode === "normal" ? "success" : (p.mode === "staggered" ? "primary" : "danger"))}</td>
    <td>${p.actions.map(a => `<div style="margin-bottom:3px">${a.auto ? tag("自动", "primary", "ri-cpu-line") : tag(a.owner, "default")} ${esc(a.text)}</div>`).join("")}</td></tr>`).join("")}
    </table>`)}</div>`);
}

/* ==================== 3. 工单处置台 ==================== */
async function pgWorkbench() {
  const list = await api("/api/incidents?limit=40");
  const SRC = { citizen: "随手拍", vision: "AI视频", iot: "传感器", asset: "扫码报修", scenario: "场景" };
  const el = h(`<div>
    ${panel("ri-todo-line", `工单处置台 ${badge(list.length, list.length > 10 ? "warn" : "")}`, "状态机：上报→派单→处理→解决→归档",
    list.length ? `<table class="tbl"><tr><th>工单号</th><th>描述</th><th>AI分类/派单</th><th>来源</th><th>状态</th><th>操作</th></tr>
    ${list.map(i => {
      const sm = SRC_META[i.source] || SRC_META.citizen;
      return `<tr><td><b>${i.ticket_no}</b><div class="muted">${fmt(i.created_at)}</div></td>
      <td style="max-width:260px">${esc(i.description)}<div class="muted"><i class="ri-map-pin-line"></i> ${esc(i.location)}</div></td>
      <td>${tag(CATL[i.category] || i.category, "primary")}<div class="muted">${esc(i.assignee || "—")} · P${i.priority}</div></td>
      <td><span style="display:inline-flex;align-items:center;gap:4px"><i class="${sm.icon}" style="color:${sm.color}"></i>${tag(SRC[i.source] || i.source, "default")}</span></td>
      <td>${tag(STL[i.status], i.status === "resolved" || i.status === "closed" ? "success" : (i.status === "processing" ? "warning" : "primary"))}</td>
      <td>${nextBtn(i)}</td></tr>`}).join("")}</table>` : empty("ri-todo-line", "暂无工单"))}</div>`);
  return el;
}
function nextBtn(i) {
  const nxt = { dispatched: ["processing", "开始处理"], processing: ["resolved", "标记解决"], resolved: ["closed", "归档"] }[i.status];
  return nxt ? btn(nxt[1], `advTicket('${i.ticket_no}','${nxt[0]}')`) : "—";
}
async function advTicket(no, to) {
  await api(`/api/incidents/${no}/status`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to_status: to, operator: SESSION.name })
  });
  toast("工单状态已更新");
  go(document.querySelector("nav .active").dataset.page);
}

/* ==================== 4. 风险事件（community） ==================== */
async function pgHazards() {
  const hazards = await api("/api/brain/hazards");
  const el = h(`<div>
    ${divider("多模态融合确认 · 本体推理")}
    ${panel("ri-alarm-warning-line", "活跃风险事件", "",
    `<div id="hz-box">${hazards.length ? "" : empty("ri-shield-check-line", "当前无活跃风险")}</div>`)}</div>`);
  const box = el.querySelector("#hz-box");
  hazards.forEach(hz => {
    const borderColor = sevBorder(hz.severity);
    const item = h(`<div class="list-item" style="cursor:pointer;border-left-color:${borderColor};border-left-width:4px">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      ${tag(SEV[hz.severity], SEVT[hz.severity])} <i class="${HZI[hz.hazard_class] || "ri-alert-line"}" style="color:var(--brand)"></i>
      <b>${HZL[hz.hazard_class] || hz.hazard_class}</b> <span class="muted">@ ${esc(hz.zone)}</span>
      <span style="margin-left:auto">${btn(hz.status === "active" ? "开始处置" : "标记解除", `event.stopPropagation();advanceHazard(${hz.id})`, { theme: "default", variant: "outline" })}</span></div>
      ${hz.suggestion ? `<div class="notice important" style="margin-top:8px;margin-bottom:0"><i class="ri-lightbulb-flash-line"></i><div class="bd"><b>处置建议</b><div class="muted">${esc(hz.suggestion)}</div></div></div>` : ""}
      <div class="chain-wrap" style="max-height:0;overflow:hidden;transition:max-height .4s ease">
        <pre class="chain">${esc(hz.inference)}</pre></div></div>`).firstChild;
    /* 推理链展开动画 */
    item.onclick = () => {
      const wrap = item.querySelector(".chain-wrap");
      if (wrap.style.maxHeight === "0px" || wrap.style.maxHeight === "") {
        wrap.style.maxHeight = wrap.scrollHeight + "px";
      } else {
        wrap.style.maxHeight = "0px";
      }
    };
    box.appendChild(item);
  });
  return el;
}

/* ==================== 5. 通知中心（parent/teacher） ==================== */
async function pgInbox() {
  const list = await api(`/api/notifications/inbox/${SESSION.user_id}`);
  const el = h(`<div>
    ${divider("定向到人 · 回执可查 · 紧急未读15分钟升级电话补呼")}
    ${panel("ri-notification-3-line", "通知中心", "",
    `<div id="nb">${list.length ? "" : empty("ri-mail-check-line", "暂无通知")}</div>`)}</div>`);
  const box = el.querySelector("#nb");
  const LVL = { info: "普通", important: "重要", emergency: "紧急·需回执" };
  const LVI = { info: "ri-information-line", important: "ri-error-warning-line", emergency: "ri-alarm-warning-line" };
  const LVC = { info: C_BLUE, important: C_ORANGE, emergency: C_RED };
  list.forEach(n => {
    const borderColor = LVC[n.level] || C_BLUE;
    const item = h(`<div class="list-item" style="border-left-color:${borderColor};border-left-width:3px">
      <div style="display:flex;align-items:center;gap:8px">
        <i class="${LVI[n.level] || "ri-information-line"}" style="color:${borderColor};font-size:17px"></i>
        <div class="bd" style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
            <b>${esc(n.title)}</b>
            ${!n.read_at ? statusDot("online", "未读") : ""}
            ${n.read_at ? tag("已读", "success") : tag("未读", "danger")}
          </div>
          <div class="muted" style="margin-top:4px">${fmt(n.created_at)} · ${esc(n.created_by)} · ${LVL[n.level]}</div>
          <div style="margin-top:6px;white-space:pre-wrap;max-height:76px;overflow:hidden;cursor:pointer;transition:max-height .3s ease" class="nbody">${esc(n.body)}</div>
          ${n.read_at ? "" : `<div style="margin-top:8px" class="receipt-wrap">${btn("我已知晓（回执）", `readNotif(${n.id},this)`, { icon: "ri-check-line" })}</div>`}
        </div>
      </div></div>`).firstChild;
    item.querySelector(".nbody").onclick = e => { e.target.style.maxHeight = e.target.style.maxHeight ? "" : "none" };
    box.appendChild(item);
  });
  return el;
}
async function readNotif(id, btnEl) {
  await api(`/api/notifications/${id}/read/${SESSION.user_id}`, { method: "POST" });
  /* 回执确认动画 */
  const wrap = btnEl.closest(".receipt-wrap");
  wrap.innerHTML = `<span style="display:inline-flex;align-items:center;gap:4px;color:#2ba471;font-size:13px;animation:fadein .3s ease"><i class="ri-checkbox-circle-line"></i> 回执已提交</span>`;
}

/* ==================== 6. 孩子空间（parent 内嵌，一人一档） ==================== */
async function pgChild() {
  if (!CHILD) return h(empty("ri-user-heart-line", "未关联孩子档案"));
  const p = await api(`/api/children/${CHILD.id}/profile?operator_id=${SESSION.user_id}`);
  const s = p.student, hr = p.health_records, f = p.fitness;
  /* 成绩等级映射为百分比 */
  const levelPct = { "优": 95, "良": 78, "中": 60, "待提高": 35 };
  const levelColor = { "优": C_GREEN, "良": C_BLUE, "中": C_ORANGE, "待提高": C_RED };
  const el = h(`<div>
    <!-- 签名时刻：profile-hero 光斑装饰 -->
    <div class="panel"><div class="panel-bd profile-hero">
      <div class="av">${esc(s.name.slice(-2))}</div>
      <div style="flex:1;position:relative;z-index:1">
        <div style="font-size:17px;font-weight:700">${esc(s.name)} <span class="muted" style="font-size:13px">${esc(s.class_name)}</span></div>
        <div class="muted" style="margin-top:4px"><i class="ri-price-tag-3-line"></i> 兴趣：${(s.interests || []).map(esc).join("、") || "未填"}
          ${btn("编辑", "editInterests()", { theme: "default", variant: "text", icon: "ri-edit-line" })}</div>
        <div class="muted" style="margin-top:2px"><i class="ri-shield-user-line"></i> ${esc(p.note)}</div>
      </div></div></div>
    ${metricRow([
      { icon: "ri-scales-3-line", num: p.bmi ? p.bmi.bmi : "—", label: `BMI ${p.bmi && p.bmi.status ? "·" + p.bmi.status : ""}` },
      { icon: "ri-eye-line", num: p.vision ? p.vision.latest : "—", label: "视力（较低眼）" },
      { icon: "ri-run-line", num: f.avg_score || "—", label: `体测均分 · 弱项${f.weak_items.length ? f.weak_items.length + "项" : "无"}` },
    ])}
    <div class="grid g2">
      ${panel("ri-line-chart-line", "每学期健康档案", "身高/体重/视力/龋齿纵向对比",
        `<div class="vchart" id="ch-growth"></div>
        <table class="tbl" style="margin-top:10px"><tr><th>学期</th><th>身高</th><th>体重</th><th>视力(左/右)</th><th>龋齿</th></tr>
        ${hr.map(r => `<tr><td>${r.term}</td><td>${r.height_cm}cm</td><td>${r.weight_kg}kg</td>
          <td>${r.vision_left} / ${r.vision_right}</td><td>${r.dental_caries || 0}颗</td></tr>`).join("")}</table>`)}
      ${panel("ri-mental-health-line", "健康提示", "规则引擎生成 · 非医疗诊断",
        `${p.vision && p.vision.alert ? `<div class="notice important"><i class="ri-eye-line"></i><div class="bd"><b>视力提醒</b><div class="muted">${esc(p.vision.advice)}</div><div class="muted">依据：${esc(p.vision.basis)}</div></div></div>` : ""}
        ${p.nutrition ? `<div class="notice"><i class="ri-heart-pulse-line"></i><div class="bd"><b>营养建议（${esc(p.nutrition.status)}）</b>
          ${p.nutrition.tips.map(t => `<div class="muted">· ${esc(t)}</div>`).join("")}
          ${(p.nutrition.suggest_supplements || []).length ? `<div style="margin-top:6px">建议关注补充：${p.nutrition.suggest_supplements.map(x => tag(x, "success")).join(" ")}</div>` : ""}
          <div class="muted" style="margin-top:6px">${esc(p.nutrition.disclaimer)}</div></div></div>` : ""}`)}
      ${panel("ri-run-line", "体质健康（AI 体测）", "",
        `<table class="tbl"><tr><th>学期</th><th>项目</th><th>成绩</th><th>折算分</th><th>来源</th></tr>
        ${f.records.map(r => `<tr><td>${r.term}</td><td>${esc(r.item)}</td><td>${r.value}${esc(r.unit || "")}</td>
          <td>${tag(r.score, r.score >= 90 ? "success" : (r.score < 70 ? "danger" : "primary"))}</td>
          <td>${r.source === "ai_video" ? tag("AI视频计数", "purple", "ri-cpu-line") : tag("人工", "default")}</td></tr>`).join("")}</table>
        ${f.prescriptions.map(x => `<div class="notice important" style="margin-top:10px"><i class="ri-guide-line"></i><div class="bd"><b>锻炼处方 · ${esc(x.item)}</b><div class="muted">${esc(x.plan)}</div></div></div>`).join("")}
        <div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px">
          <b style="font-size:13.5px"><i class="ri-video-upload-line" style="color:var(--brand)"></i> AI 体测打卡</b>
          <span class="muted">上传动作视频 → 骨架关键点计数，视频推理后即丢弃、只存成绩</span>
          <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;align-items:center">
            <select id="fv-item" class="native inline"><option>一分钟跳绳</option><option>仰卧起坐</option><option>开合跳</option></select>
            <input type="file" id="fv-file" accept="video/*" class="native inline" style="flex:1">
            ${btn("上传分析", "uploadFitness()", { icon: "ri-magic-line" })}</div>
          <div class="muted" style="margin-top:6px;display:flex;align-items:center;gap:4px"><i class="ri-drag-drop-line"></i> 支持拖拽视频文件到上方输入框</div>
          <div class="muted" id="fv-msg" style="margin-top:6px"></div></div>`)}
      ${panel("ri-graduation-cap-line", "成绩纵向对比", "只看自己进步 · 不显示班级排名",
        `${p.academic.map(a => `<div style="margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:2px">
            <span>${esc(a.subject)}（${a.term}）</span>${tag(a.level, a.level === "优" ? "success" : (a.level === "待提高" ? "danger" : "primary"))}
          </div>
          ${progressBar(levelPct[a.level] || 50, levelColor[a.level] || C_BLUE, "")}
        </div>`).join("")}
        <div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px">
          <b style="font-size:13.5px"><i class="ri-compass-3-line" style="color:var(--brand)"></i> 校外兴趣班登记</b>
          <span class="muted">登记后选修课不再重复推荐同项目</span>
          <div id="ec-list">${p.external_classes.map(e => `<div class="list-item">${tag(e.category, "primary")} ${esc(e.name)} · ${e.weekly_hours}h/周
            <span style="float:right">${btn("删除", `delEC(${e.id})`, { theme: "danger", variant: "text", icon: "ri-delete-bin-line" })}</span></div>`).join("") || "<div class='muted' style='margin:8px 0'>暂未登记</div>"}</div>
          <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
            <select id="ec-cat" class="native inline"><option>体育</option><option>艺术</option><option>科技</option><option>人文</option><option>劳动</option></select>
            <input id="ec-name" class="native" placeholder="机构/班级名称，如：XX游泳馆少儿班" style="flex:1;min-width:160px">
            ${btn("登记", "addEC()", { icon: "ri-add-line" })}</div></div>`)}
    </div></div>`);
  /* 身高/体重双轴趋势（渐变面积填充） */
  mount(() => chart(el.querySelector("#ch-growth"), {
    tooltip: { trigger: "axis" },
    legend: { top: 0, itemWidth: 14, textStyle: { fontSize: 11 } },
    grid: { left: 42, right: 42, top: 30, bottom: 24 },
    xAxis: { type: "category", data: hr.map(r => r.term) },
    yAxis: [{ type: "value", name: "cm", min: v => Math.floor(v.min - 5) }, { type: "value", name: "kg", min: v => Math.floor(v.min - 3), splitLine: { show: false } }],
    series: [
      { name: "身高(cm)", type: "line", smooth: true, data: hr.map(r => r.height_cm),
        itemStyle: { color: { gradient: { x1: 0, y1: 0, x2: 0, y2: 1, direction: "vertical", stops: [{ offset: 0, color: C_BLUE }, { offset: 1, color: "rgba(0,82,217,0.05)" }] } } },
        areaStyle: { color: { gradient: { x1: 0, y1: 0, x2: 0, y2: 1, stops: [{ offset: 0, color: "rgba(0,82,217,0.25)" }, { offset: 1, color: "rgba(0,82,217,0.02)" }] } } } },
      { name: "体重(kg)", type: "line", smooth: true, yAxisIndex: 1, data: hr.map(r => r.weight_kg),
        itemStyle: { color: C_ORANGE },
        areaStyle: { color: { gradient: { x1: 0, y1: 0, x2: 0, y2: 1, stops: [{ offset: 0, color: "rgba(227,115,24,0.2)" }, { offset: 1, color: "rgba(227,115,24,0.02)" }] } } } },
    ]
  }, 200));
  return el;
}
async function editInterests() {
  const cur = (CHILD.interests || []).join("、");
  const v = prompt("孩子兴趣标签（用、分隔）：", cur); if (v === null) return;
  const interests = v.split(/[、,，\s]+/).filter(Boolean);
  CHILD = await api(`/api/children/${CHILD.id}/interests?operator_id=${SESSION.user_id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ interests })
  });
  go("child");
}
async function addEC() {
  const category = document.getElementById("ec-cat").value, name = document.getElementById("ec-name").value.trim();
  if (!name) { toast("请填写机构/班级名称", "error"); return }
  await api(`/api/children/${CHILD.id}/external-classes?operator_id=${SESSION.user_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category, name, weekly_hours: 2 })
  });
  toast("已登记，选修课将不再重复推荐同项目"); go("child");
}
async function delEC(id) {
  await api(`/api/children/${CHILD.id}/external-classes/${id}?operator_id=${SESSION.user_id}`, { method: "DELETE" });
  go("child");
}
async function uploadFitness() {
  const f = document.getElementById("fv-file").files[0], msg = document.getElementById("fv-msg");
  if (!f) { msg.textContent = "请先选择视频文件"; return }
  msg.innerHTML = `<i class="ri-loader-4-line spin"></i> AI 分析中（骨架关键点提取→动作计数）…`;
  const fd = new FormData(); fd.append("item", document.getElementById("fv-item").value);
  fd.append("term", "2025-2026下"); fd.append("video", f);
  try {
    const r = await api(`/api/children/${CHILD.id}/fitness-video?operator_id=${SESSION.user_id}`, { method: "POST", body: fd });
    msg.innerHTML = `<i class="ri-checkbox-circle-line" style="color:#2ba471"></i> ${esc(r.message)}<br>规范性提示：${(r.issues || []).map(esc).join("；") || "动作标准"} · ${tag("原始视频已丢弃", "success")}`;
  } catch (e) { msg.textContent = "失败：" + e.message }
}

/* ==================== 7. 选修课（parent · AI千人千面推荐） ==================== */
async function pgCourses() {
  if (!CHILD) return h(empty("ri-book-open-line", "未关联孩子档案"));
  const persona = localStorage.getItem("rq-personalized") !== "off";
  const q = persona ? `?student_id=${CHILD.id}&operator_id=${SESSION.user_id}&personalized=true` : "?personalized=false";
  const [courses, enrolls] = await Promise.all([
    api("/api/courses" + q), api(`/api/courses/enrollments/${CHILD.id}?operator_id=${SESSION.user_id}`)]);
  const el = h(`<div>
    <div class="notice" style="border-left-width:4px;${persona ? "background:rgba(0,82,217,.08)" : ""}">
      <i class="ri-magic-line"></i><div class="bd" style="flex:1"><b>${esc(CHILD.name)} 的选修课${persona ? "（AI个性化排序）" : "（目录原序）"}</b>
      <span class="muted">依据：体测弱项/健康趋势/成绩扬长补短/兴趣/校外班排除/时段冲突 六因子</span></div>
      <span style="flex:none">${btn(persona ? "关闭个性化" : "开启个性化", "togglePersona()", { theme: persona ? "primary" : "default", variant: "outline", icon: "ri-shuffle-line" })}</span></div>
    <div class="grid g2">
    <div>
      ${courses.map(c => `<div class="course ${c.tag === "优先推荐" ? "rec" : ""}">
        <div class="ttl"><b>${esc(c.name)}</b> ${tag(c.category, "primary")}
        ${c.tag === "优先推荐" ? tag("优先推荐", "success", "ri-star-fill") : ""}
        ${c.tag === "探索推荐" ? tag("探索推荐 · 防茧房", "purple", "ri-compass-3-line") : ""}
        ${c.excluded ? tag("校外已学 · 不重复推荐", "default") : ""}
        ${c.conflict ? tag(c.conflict, "warning") : ""}</div>
        <div class="muted" style="margin-top:5px"><i class="ri-time-line"></i> ${WD[c.weekday]} ${c.time_slot} · ${esc(c.teacher)} · 名额 ${c.enrolled}/${c.capacity}</div>
        <div class="route-bar"><i style="width:${c.capacity ? Math.min(c.enrolled / c.capacity * 100, 100) : 0}%;background:${c.enrolled >= c.capacity ? "linear-gradient(90deg,#d54941,#e37318)" : "linear-gradient(90deg,var(--brand),#28d1e8)"}"></i></div>
        ${c.reasons.length ? `<div class="why" style="max-height:60px;overflow:hidden;transition:max-height .3s ease;cursor:pointer" onclick="this.style.maxHeight=this.style.maxHeight?'':'none'">${c.reasons.map(r => `<div><i class="ri-arrow-right-s-line"></i>${esc(r)}</div>`).join("")}</div>` : ""}
        <div style="margin-top:10px">${c.conflict === "已报名本课"
          ? btn("退课", `cancelCourse(${c.id})`, { theme: "danger", variant: "outline", icon: "ri-close-line" })
          : (c.conflict ? "" : btn("报名", `enrollCourse(${c.id},'${esc(c.name)}')`, { icon: "ri-add-line" }))}
        </div></div>`).join("")}
    </div>
    ${panel("ri-file-list-3-line", "已报课程", "推荐理由留痕",
      (enrolls.length ? enrolls.map(e => `<div class="list-item"><b>${esc(e.name)}</b> ${tag(e.category, "primary")}
        <div class="muted"><i class="ri-time-line"></i> ${WD[e.weekday]} ${e.time_slot} · ${esc(e.teacher)}</div>
        <div class="muted" style="margin-top:4px"><i class="ri-bookmark-line"></i> ${esc(e.reason_snapshot || "")}</div></div>`).join("") : empty("ri-file-list-3-line", "暂未报名")) +
      `<div class="muted" style="margin-top:10px">报名时点的推荐理由做快照留存，可追溯「当时为什么推荐」。</div>`)}
    </div></div>`);
  return el;
}
function togglePersona() {
  const cur = localStorage.getItem("rq-personalized") !== "off";
  localStorage.setItem("rq-personalized", cur ? "off" : "on"); go("courses");
}
async function enrollCourse(id, name) {
  try {
    const r = await api(`/api/courses/${id}/enroll`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: CHILD.id, operator_parent_id: SESSION.user_id, reason: `家长为孩子报名「${name}」` })
    });
    toast("报名成功！" + (r.reason_snapshot || "")); go("courses");
  } catch (e) { toast("报名失败：" + e.message, "error") }
}
async function cancelCourse(id) {
  if (!confirm("确认退课？")) return;
  try {
    await api(`/api/courses/${id}/cancel`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: CHILD.id, operator_parent_id: SESSION.user_id })
    }); go("courses");
  } catch (e) { toast("退课失败：" + e.message, "error") }
}

/* ==================== 8. 请假（parent） ==================== */
async function pgLeave() {
  if (!CHILD) return h(empty("ri-calendar-event-line", "未关联孩子档案"));
  const list = await api(`/api/leave/by-student/${CHILD.id}?operator_id=${SESSION.user_id}`);
  const today = new Date().toISOString().slice(0, 10);
  const LST = { approved: ["已批准", "success"], pending: ["待班主任审批", "warning"], rejected: ["未批准", "danger"] };
  const el = h(`<div class="grid g2">
    ${panel("ri-edit-line", `为 ${esc(CHILD.name)} 请假`, "",
      `<div class="form-row"><label>开始日期</label><input type="date" id="lv-start" class="native" value="${today}"></div>
      <div class="form-row"><label>结束日期</label><input type="date" id="lv-end" class="native" value="${today}"></div>
      <div class="form-row"><label>类型</label>
      <select id="lv-type" class="native" onchange="document.getElementById('lv-sym').style.display=this.value==='sick'?'block':'none'">
        <option value="sick">病假</option><option value="personal">事假</option></select></div>
      <div id="lv-sym" class="form-row"><label>症状（病假必填 · 用于全校缺勤聚集健康监测，脱敏聚合）</label>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px">
        ${["发热", "咳嗽", "呕吐", "腹泻", "皮疹", "其他"].map(s =>
          `<button type="button" class="sym-pill t-tag t-tag--default t-tag--light" onclick="this.classList.toggle('t-tag--primary');this.classList.toggle('t-tag--default')" data-sym="${s}" style="border-radius:999px;cursor:pointer;transition:all .15s ease">${s}</button>`).join("")}</div></div>
      <div class="form-row"><label>备注</label><textarea id="lv-note" class="native" rows="2" placeholder="补充说明（选填）"></textarea></div>
      ${btn("提交请假", "submitLeave()", { icon: "ri-send-plane-fill", size: "m" })}
      <div class="muted" id="lv-msg" style="margin-top:8px"></div>
      <div class="muted" style="margin-top:10px"><i class="ri-shield-check-line"></i> 病假症状只用于同班聚集性缺勤预警（3天内同症状≥3例触发校医排查），不对外公开个人信息。</div>`)}
    ${panel("ri-history-line", "请假记录", "班主任、校长可见台账",
      list.length ? `<div class="leave-timeline">${list.map(l => `<div class="list-item" style="border-left-width:3px;border-left-color:${l.status === "approved" ? C_GREEN : (l.status === "pending" ? C_ORANGE : C_RED)}">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          <b>${l.start_date}${l.end_date !== l.start_date ? " ~ " + l.end_date : ""}</b>
          ${tag(LVT[l.leave_type], "primary")} ${tag(l.days + "天(按工作日)", "default")}
          ${tag(LST[l.status][0], LST[l.status][1])}
        </div>
        <div class="muted" style="margin-top:3px">${(l.symptoms || []).map(esc).join("、")}${l.note ? " · " + esc(l.note) : ""}${l.approved_by ? " · 审批人：" + esc(l.approved_by) : ""}</div></div>`).join("")}</div>` : empty("ri-calendar-check-line", "暂无请假记录"))}
  </div>`);
  return el;
}
async function submitLeave() {
  const msg = document.getElementById("lv-msg");
  /* 收集 pill 按钮选中的症状 */
  const symptoms = [...document.querySelectorAll(".sym-pill.t-tag--primary")].map(c => c.dataset.sym);
  const body = {
    student_id: CHILD.id, parent_id: SESSION.user_id,
    start_date: document.getElementById("lv-start").value, end_date: document.getElementById("lv-end").value,
    leave_type: document.getElementById("lv-type").value,
    symptoms: symptoms.length ? symptoms : null, note: document.getElementById("lv-note").value || null
  };
  try {
    const r = await api("/api/leave", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    toast(`已提交（${r.days}天，待班主任审批）`); go("leave");
  } catch (e) { msg.textContent = "失败：" + e.message }
}

/* ==================== 9. 用餐日历（parent · 月勾选 + 后付费账单） ==================== */
async function pgMeals() {
  if (!CHILD) return h(empty("ri-restaurant-line", "未关联孩子档案"));
  const month = curMonth();
  const [plan, bill] = await Promise.all([
    api(`/api/meals/plan/${CHILD.id}/${month}?operator_id=${SESSION.user_id}`),
    api(`/api/meals/bill/${CHILD.id}/${month}?operator_id=${SESSION.user_id}`)]);
  const checked = new Set(plan ? plan.days : []);
  const [y, m] = month.split("-").map(Number);
  const first = new Date(y, m - 1, 1), dim = new Date(y, m, 0).getDate();
  const lead = (first.getDay() + 6) % 7;
  let cells = "";
  for (let i = 0; i < lead; i++) cells += "<div class='d blank'></div>";
  for (let d = 1; d <= dim; d++) {
    const dow = new Date(y, m - 1, d).getDay();
    const wk = dow === 0 || dow === 6;
    cells += `<div class="d ${wk ? "off" : (checked.has(d) ? "on" : "")}" data-d="${d}" ${wk ? "" : `onclick="toggleMealDay(this)"`}>${d}</div>`;
  }
  const el = h(`<div class="grid g2">
    ${panel("ri-calendar-todo-line", `${month} 用餐日历（${esc(CHILD.name)}）`, "",
      `${plan && plan.billed ? tag("本月已出账 · 锁定", "default", "ri-lock-line") : ""}
      <div class="muted">勾选在校用餐的日子（周末不供餐）。原来在微信群里接龙报饭，现在在这里管起来——后厨按勾选人数备餐，班主任能看到台账。</div>
      <div class="cal"><div class="hd">一</div><div class="hd">二</div><div class="hd">三</div><div class="hd">四</div><div class="hd">五</div><div class="hd">六</div><div class="hd">日</div>${cells}</div>
      ${plan && plan.billed ? "" : `<div style="margin-top:12px">${btn("保存本月用餐安排", `saveMeals('${month}')`, { icon: "ri-check-line", size: "m" })}</div>`}
      <div class="muted" id="ml-msg" style="margin-top:8px"></div>
      <div class="muted" style="margin-top:8px">请假获批时若与用餐日重叠，系统只做提示、由家长自行调整——不自动动钱。</div>`)}
    ${panel("ri-bank-card-line", "本月账单预览", "后付费 · 无余额",
      `<div style="display:flex;justify-content:center;margin:var(--sp-4) 0">
        ${heroStat("ri-money-cny-circle-line", "¥" + bill.amount, "本月餐费", `${bill.days_count}天 × ¥${bill.price_per_meal}/餐`)}
      </div>
      <div class="notice"><i class="ri-money-cny-circle-line"></i><div class="bd"><b>缴费方式</b><div class="muted">${esc(bill.payment)}</div></div></div>
      ${metricRow([
        { icon: "ri-calendar-check-line", num: bill.days_count, label: "用餐天数" },
        { icon: "ri-money-cny-circle-line", num: "¥" + bill.price_per_meal, label: "单餐价格" },
      ])}`)}
  </div>`);
  return el;
}
function toggleMealDay(el) { el.classList.toggle("on") }
async function saveMeals(month) {
  const days = [...document.querySelectorAll(".cal .d.on")].map(x => Number(x.dataset.d));
  const msg = document.getElementById("ml-msg");
  try {
    await api("/api/meals/plan", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: CHILD.id, parent_id: SESSION.user_id, month, days })
    });
    toast("已保存本月用餐安排"); go("meals");
  } catch (e) { msg.textContent = "失败：" + e.message }
}

/* ==================== 10. 请假·缺勤（teacher） ==================== */
async function pgLeaveAdmin() {
  const cls = SESSION.extra?.manage_class || "六年级1班";
  const [pending, stats, watch, forecast] = await Promise.all([
    api(`/api/leave/pending?operator_id=${SESSION.user_id}`),
    api(`/api/leave/class-stats?class_name=${encodeURIComponent(cls)}&operator_id=${SESSION.user_id}`),
    api(`/api/leave/illness-watch?operator_id=${SESSION.user_id}`),
    api("/api/meals/kitchen-forecast")]);
  const watchRows = watch.classes.flatMap(c => c.symptoms.map(s => ({ cls: c.class_name, ...s })));
  const el = h(`<div>
    ${watchRows.length ? `<div class="notice emergency" style="animation:pulse 1.5s infinite"><i class="ri-virus-line"></i><div class="bd"><b>缺勤聚集预警（近${watch.window_days}天 同班同症状≥${watch.threshold}例）</b>
      ${watchRows.map(w => `<div class="muted">${esc(w.cls)} · ${esc(w.symptom)} × ${w.count}例 —— 已进入多模态风险融合，建议配合校医排查</div>`).join("")}</div></div>`
      : `<div class="notice"><i class="ri-stethoscope-line"></i><div class="bd"><b>症状监测正常</b> <span class="muted">近${watch.window_days}天无同班同症状≥${watch.threshold}例的聚集（数据来源：请假台账症状标签，脱敏聚合）</span></div></div>`}
    ${divider("请假审批 · 缺勤统计 · 备餐联动")}
    <div class="grid g2">
    ${panel("ri-time-line", `待审批请假 ${badge(pending.length, pending.length > 5 ? "danger" : "warn")}`, "",
      pending.length ? pending.map(l => `<div class="list-item" style="border-left-color:${C_ORANGE};border-left-width:3px"><b>${esc(l.student_name)}</b> · ${l.start_date}${l.end_date !== l.start_date ? " ~ " + l.end_date : ""}
        ${tag(LVT[l.leave_type], "primary")} ${tag(l.days + "天", "default")}
        <div class="muted">${(l.symptoms || []).map(esc).join("、")}${l.note ? " · " + esc(l.note) : ""}</div>
        <div style="margin-top:8px;display:flex;gap:8px">${btn("批准", `approveLeave(${l.id},true)`, { icon: "ri-check-line" })}
        ${btn("不批", `approveLeave(${l.id},false)`, { theme: "danger", variant: "outline", icon: "ri-close-line" })}</div></div>`).join("") : empty("ri-checkbox-circle-line", "暂无待审批"))}
    ${panel("ri-bar-chart-grouped-line", `${esc(cls)} 缺勤统计`, "首次能看到每个孩子本月/本学期请了几天假",
      `<div class="vchart" id="ch-absent"></div>
      <table class="tbl" style="margin-top:8px"><tr><th>学生</th><th>本月</th><th>本学期</th><th>病假</th><th>事假</th></tr>
      ${stats.stats.map(s => `<tr><td>${esc(s.student_name)}</td><td>${s.month_days}天</td><td><b>${s.term_days}</b>天</td>
        <td>${s.sick_days}天</td><td>${s.personal_days}天</td></tr>`).join("")}</table>`)}
    <div class="span2">${panel("ri-restaurant-2-line", "今日备餐台账", "联动家长用餐日历",
      forecast.by_class.length ? `<div class="metric-row" style="margin-bottom:var(--sp-3)">${metricRow([
        { icon: "ri-group-line", num: forecast.total + "人", label: "合计用餐" }
      ])}</div>
      <table class="tbl"><tr><th>班级</th><th>人数</th></tr>${forecast.by_class.map(c => `<tr><td>${esc(c.class_name)}</td><td><b>${c.count}</b>人</td></tr>`).join("")}</table>
      <div class="muted" style="margin-top:6px">${esc(forecast.note)}</div>`
      : empty("ri-restaurant-line", `今日（${forecast.date}）无用餐登记 · ${forecast.note}`))}</div>
    </div></div>`);
  /* 学期请假天数条形图：渐变色堆叠 */
  mount(() => chart(el.querySelector("#ch-absent"), {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0, itemWidth: 14, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 16, top: 28, bottom: 24 },
    xAxis: { type: "value", minInterval: 1 },
    yAxis: { type: "category", data: stats.stats.map(s => s.student_name) },
    series: [
      { name: "病假", type: "bar", stack: "t", data: stats.stats.map(s => s.sick_days),
        itemStyle: { color: { gradient: { x1: 0, y1: 0, x2: 0, y2: 1, stops: [{ offset: 0, color: C_ORANGE }, { offset: 1, color: "rgba(227,115,24,0.3)" }] } }, borderRadius: [0, 0, 0, 0] },
        barMaxWidth: 16 },
      { name: "事假", type: "bar", stack: "t", data: stats.stats.map(s => s.personal_days),
        itemStyle: { color: { gradient: { x1: 0, y1: 0, x2: 0, y2: 1, stops: [{ offset: 0, color: C_BLUE }, { offset: 1, color: "rgba(0,82,217,0.3)" }] } }, borderRadius: [0, 4, 4, 0] },
        barMaxWidth: 16 },
    ]
  }, Math.max(140, stats.stats.length * 34 + 50)));
  return el;
}
async function approveLeave(id, ok) {
  const comment = ok ? "" : prompt("不批准原因：", "请补充说明后重新提交");
  if (!ok && comment === null) return;
  try {
    const r = await api(`/api/leave/${id}/approve`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operator_id: SESSION.user_id, approve: ok, comment: comment || null })
    });
    let m = ok ? "已批准" : "已退回";
    if (r.meal_suggestion) m += "；" + r.meal_suggestion;
    if (r.illness_watch && r.illness_watch.length) m += "；触发缺勤聚集监测：" + r.illness_watch.map(w => `${w.symptom}×${w.count}例`).join("、");
    toast(m); go("leaveadmin");
  } catch (e) { toast("失败：" + e.message, "error") }
}

/* ==================== 11. 年检公示墙（admin管理 / teacher·parent公示） ==================== */
async function pgInspections() {
  const isAdmin = SESSION.role === "admin";
  const reqs = [api("/api/inspections"), api("/api/inspections/desk-fit")];
  if (isAdmin) reqs.push(api("/api/inspections/retirement-list"));
  const [insp, fit, retire] = await Promise.all(reqs);
  /* 课桌椅匹配率圆环参数 */
  const fitPct = Math.round(fit.fit_rate * 100);
  const circumference = 2 * Math.PI * 42;
  const offset = circumference * (1 - fit.fit_rate);
  const ringColor = fit.fit_rate >= 0.9 ? C_GREEN : (fit.fit_rate >= 0.7 ? C_ORANGE : C_RED);
  const el = h(`<div>
    <div class="data-grid">
      ${heroStat("ri-shield-check-line", insp.summary.total, "年检门类", "甲醛/直饮水/消防/照明/体育器械/急救箱/课桌椅")}
      ${heroStat("ri-alarm-warning-line", insp.summary.overdue, "已超期未复检", "", insp.summary.overdue ? "bad" : "good")}
      ${heroStat("ri-timer-flash-line", insp.summary.due_soon, "30天内临期", "", insp.summary.due_soon ? "warn" : "good")}
      ${heroStat("ri-close-circle-line", insp.summary.failed, "检查不合格项", "", insp.summary.failed ? "bad" : "good")}
    </div>
    ${insp.alerts.length ? `<div class="notice important"><i class="ri-flask-line"></i><div class="bd"><b>效期规则引擎提醒</b>${insp.alerts.map(a => `<div class="muted">${esc(a)}</div>`).join("")}</div></div>` : ""}
    ${panel("ri-survey-line", "安全年检公示墙", "每年检查一次 · 检化验报告编号可查",
      `<table class="tbl"><tr><th>门类</th><th>对象</th><th>检查项</th><th>结果</th><th>检查日期</th><th>下次到期</th><th>状态</th></tr>
      ${insp.records.map(r => {
        const isOverdue = r.due_status === "已超期";
        const isDue = r.due_status === "临期";
        const rowBorder = isOverdue ? C_RED : (isDue ? C_ORANGE : "transparent");
        return `<tr style="border-left:3px solid ${rowBorder}"><td>${tag(r.category_label, "primary")}</td>
        <td>${esc(r.target)}</td><td>${esc(r.item)}${r.report_no ? `<div class="muted">报告号 ${r.report_no}</div>` : ""}</td>
        <td>${r.passed ? `<i class="ri-checkbox-circle-line" style="color:#2ba471"></i>` : `<i class="ri-close-circle-line" style="color:#d54941"></i>`} ${esc(r.result)}</td>
        <td class="muted">${r.inspect_date}</td><td class="muted">${r.next_due || "—"}</td>
        <td>${tag(r.due_status, r.due_status === "已超期" ? "danger" : (r.due_status === "临期" ? "warning" : "success"))}</td></tr>`}).join("")}</table>`)}
    <div class="grid g2">
      ${panel("ri-armchair-line", "课桌椅身高匹配", "GB/T 3976 联动体检档案",
        <!-- 匹配率用圆环+大数字展示 -->
        `<div style="display:flex;justify-content:center;align-items:center;gap:var(--sp-5);padding:var(--sp-4) 0">
          <div class="progress-ring">
            <svg width="100" height="100" viewBox="0 0 100 100">
              <circle class="ring-bg" cx="50" cy="50" r="42"></circle>
              <circle class="ring-fg" cx="50" cy="50" r="42" style="stroke:${ringColor};stroke-dasharray:${circumference};stroke-dashoffset:${offset}"></circle>
            </svg>
            <div class="ring-val" style="position:absolute;color:${ringColor}">${fitPct}%</div>
          </div>
          <div>
            <div class="muted">当前配置：${esc(fit.current_model)} · 抽检${fit.sampled}人</div>
            ${fit.need_adjust.length ? `<div style="margin-top:6px;color:${fit.need_adjust.length > 5 ? C_RED : C_ORANGE};font-size:13px"><i class="ri-alert-line"></i> ${fit.need_adjust.length}人需调整</div>` : ""}
          </div>
        </div>
        ${fit.need_adjust.map(x => `<div class="list-item"><i class="ri-pencil-ruler-2-line" style="color:var(--brand)"></i> ${esc(x.student_name || x.student || "同学")}：建议调整为 ${esc(x.suggest)}</div>`).join("") || "<div class='muted' style='margin-top:8px'>全部匹配</div>"}
        <div class="muted" style="margin-top:8px">${esc(fit.note)}</div>`)}
      ${isAdmin && retire ? panel("ri-recycle-line", "资产超龄淘汰清单", "规则引擎自动生成",
        retire.length ? retire.map(r => `<div class="list-item" style="border-left-color:${C_RED};border-left-width:3px"><b>${esc(r.name)}</b> ${tag(r.code, "default")}
          <div class="muted">${esc(r.location)} · ${r.quantity}件 · ${r.purchased_year}年购置</div>
          <div class="muted" style="color:#d54941"><i class="ri-alert-line"></i> ${esc(r.reason)}</div>
          <div class="muted"><i class="ri-lightbulb-flash-line"></i> ${esc(r.suggestion)}</div></div>`).join("") : empty("ri-recycle-line", "暂无需淘汰资产"))
      : panel("ri-information-line", "关于本公示", "",
        `<div class="muted" style="line-height:2.1">· 甲醛/空气检测覆盖翻新教室，报告编号可向学校核验<br>· 直饮水机滤芯与水质按效期规则自动提醒复检<br>· 体育器械不合格项立即停用并公示<br>· 课桌椅匹配只公示比例与调整建议，不公示孩子身高</div>`)}
    </div></div>`);
  return el;
}

/* ==================== 12. 资产管理（admin 专属） ==================== */
async function pgAssets() {
  const oid = SESSION.user_id;
  const [summary, assets, retire] = await Promise.all([
    api(`/api/assets-summary?operator_id=${oid}`), api(`/api/assets?operator_id=${oid}`),
    api("/api/inspections/retirement-list")]);
  const retireCodes = new Set(retire.map(r => r.code));
  const grades = summary.filter(s => s.grade);
  /* 成色对应色：1=报废红 2=差橙 3=中黄 4=良青 5=全新绿 */
  function condColor(c) { return c <= 1 ? C_RED : (c <= 2 ? C_ORANGE : (c <= 3 ? "#e8a52e" : (c <= 4 ? C_CYAN : C_GREEN))); }
  const el = h(`<div>
    ${panel("ri-bar-chart-grouped-line", "各年级资产成色", "1=报废 5=全新 · 校长专属视图",
      `<div class="vchart" id="ch-cond"></div>`)}
    ${panel("ri-archive-drawer-line", "资产明细", "扫码报修任何角色可用 → 自动生成设施工单派总务处",
      `<table class="tbl"><tr><th>资产码</th><th>名称</th><th>位置</th><th>购置</th><th>成色</th><th>报修</th></tr>
      ${assets.map(a => `<tr style="border-left:3px solid ${condColor(a.condition)}">
        <td><b>${a.code}</b>${a.air_device_id ? `<div>${tag("联动空气监测", "primary", "ri-haze-2-line")}</div>` : ""}
        ${retireCodes.has(a.code) ? `<div>${tag("建议淘汰", "danger", "ri-recycle-line")}</div>` : ""}</td>
        <td>${esc(a.name)} ×${a.quantity}</td><td>${esc(a.location)}</td><td>${a.purchased_year || "—"}</td>
        <td>${rateStars(a.condition)} <span class="muted">${a.condition}/5</span></td>
        <td>${btn("扫码报修", `reportAsset('${a.code}')`, { theme: "default", variant: "outline", icon: "ri-qr-scan-2-line" })}</td></tr>`).join("")}</table>`)}
    </div>`);
  /* 年级资产成色条形图：渐变色+圆角 */
  mount(() => chart(el.querySelector("#ch-cond"), {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0, itemWidth: 14, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 16, top: 30, bottom: 24 },
    xAxis: { type: "category", data: grades.map(s => s.grade + "年级") },
    yAxis: { type: "value", max: 5, minInterval: 1 },
    series: [
      { name: "平均成色", type: "bar", data: grades.map(s => ({
        value: s.avg_condition,
        itemStyle: { color: { gradient: { x1: 0, y1: 0, x2: 0, y2: 1, stops: [{ offset: 0, color: s.avg_condition < 3 ? C_RED : C_CYAN }, { offset: 1, color: s.avg_condition < 3 ? "rgba(213,73,65,0.3)" : "rgba(15,168,189,0.2)" }] } },
        borderRadius: [4, 4, 0, 0] }
      })), barMaxWidth: 26, label: { show: true, position: "top", fontSize: 11 } },
      { name: "最差单件", type: "line", data: grades.map(s => s.worst), itemStyle: { color: C_ORANGE }, lineStyle: { type: "dashed" } },
    ]
  }, 210));
  return el;
}
async function reportAsset(code) {
  const desc = prompt(`资产 ${code} 报修描述（模拟扫二维码后填写）：`, "课桌腿松动摇晃");
  if (!desc) return;
  const r = await api(`/api/assets/${code}/report`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reporter_id: SESSION.user_id, description: desc })
  });
  toast(`报修成功！工单 ${r.ticket_no} 已派 ${r.assignee}`); go("assets");
}

/* ==================== 13. 场馆点评（teacher · 教师口碑+差评规避） ==================== */
async function pgVenues() {
  const [rep, resources] = await Promise.all([api("/api/venue-reputation"), api("/api/resources")]);
  const bookable = resources.filter(r => r.capacity);
  const el = h(`<div>
    ${divider("场馆口碑榜 · 带班老师亲历点评")}
    <div class="grid g2">
    <div>
      ${rep.map(v => `<div class="list-item" style="border-left:3px solid ${v.avg_rating >= 4 ? C_GREEN : (v.avg_rating >= 3 ? C_ORANGE : C_RED)};cursor:default">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <b>${esc(v.name)}</b> ${tag(v.category, "primary")}
          ${v.avg_rating ? `<span style="font-size:24px;font-weight:800;color:${v.avg_rating >= 4 ? C_GREEN : (v.avg_rating >= 3 ? C_ORANGE : C_RED)};font-family:Bahnschrift,'DIN Alternate','Segoe UI',var(--app-font)">${v.avg_rating}</span> <span class="muted">(${v.review_count}条)</span>` : '<span class="muted">暂无点评</span>'}
        </div>
        ${v.warning ? `<div class="notice important" style="margin-top:8px;margin-bottom:0;border-left-color:${C_RED}"><i class="ri-thumb-down-line" style="color:${C_RED}"></i><div class="bd"><b>差评规避提示</b><div class="muted">${esc(v.warning)}</div></div></div>` : ""}
        <div style="margin-top:6px">${btn("查看点评", `loadReviews(${v.resource_id},this)`, { theme: "default", variant: "text", icon: "ri-chat-smile-2-line" })}</div>
        <div class="rv-box"></div></div>`).join("")}
    </div>
    ${panel("ri-edit-line", "写点评", "仅教师/校长",
      `<div class="form-row"><label>场馆</label>
      <select id="rv-res" class="native">${bookable.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join("")}</select></div>
      <div class="form-row"><label>评分</label>
      <select id="rv-rating" class="native"><option value="5">5 星 · 强烈推荐</option><option value="4">4 星 · 推荐</option><option value="3">3 星 · 一般</option><option value="2">2 星 · 不推荐</option><option value="1">1 星 · 强烈不推荐</option></select></div>
      <div class="form-row"><label>带班体验</label>
      <textarea id="rv-comment" class="native" rows="4" placeholder="例：场地宽敞但更衣室少，40人以上建议分两批…"></textarea></div>
      <div class="form-row"><label>到访日期</label><input type="date" id="rv-date" class="native" value="${new Date().toISOString().slice(0, 10)}"></div>
      ${btn("发布点评", "submitReview()", { icon: "ri-send-plane-fill", size: "m" })}
      <div class="muted" id="rv-msg" style="margin-top:8px"></div>
      <div class="muted" style="margin-top:8px">评分≤2星会自动置顶为「差评规避提示」，帮助后续班级避坑。</div>`)}
    </div></div>`);
  return el;
}
async function loadReviews(rid, btnEl) {
  const box = btnEl.closest(".list-item").querySelector(".rv-box");
  if (box.innerHTML) { box.innerHTML = ""; return }
  const list = await api(`/api/venue-reviews/${rid}`);
  box.innerHTML = list.length ? list.map(v => `<div class="notice" style="margin-top:6px;margin-bottom:0"><i class="ri-user-star-line"></i><div class="bd">
    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">${rateStars(v.rating)} <b>${esc(v.teacher_name)}</b> <span class="muted"><i class="ri-time-line"></i> ${v.visit_date}</span></div>
    <div class="muted" style="margin-top:4px">${esc(v.comment)}</div></div></div>`).join("") : "<div class='muted' style='margin-top:6px'>暂无点评</div>";
}
async function submitReview() {
  const msg = document.getElementById("rv-msg");
  try {
    await api("/api/venue-reviews", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resource_id: Number(document.getElementById("rv-res").value),
        teacher_id: SESSION.user_id, rating: Number(document.getElementById("rv-rating").value),
        comment: document.getElementById("rv-comment").value.trim(),
        visit_date: document.getElementById("rv-date").value
      })
    });
    toast("点评已发布"); go("venues");
  } catch (e) { msg.textContent = "失败：" + e.message }
}

/* ==================== 14. 安全出行（parent） ==================== */
async function pgTravel() {
  const wd = Math.min(Math.max(new Date().getDay(), 1), 5) - 1;
  const [commute, pickup, parking, cur] = await Promise.all([
    api("/api/brain/routes/commute"), api(`/api/safety/pickup?weekday=${wd}`),
    api("/api/resources/parking"), api("/api/brain/plan/current")]);
  const cls = SESSION.extra?.child_class || SESSION.extra?.class || "六年级1班";
  const mine = pickup.find(p => p.class_name === cls) || pickup.find(p => cls.startsWith(p.class_name.slice(0, 3)));
  const RL = { recommended: ["推荐", "success"], caution: ["注意", "warning"], avoid: ["避开", "danger"] };
  const el = h(`<div>
    ${cur.mode !== "normal" ? `<div class="notice emergency"><i class="ri-alarm-warning-line"></i><div class="bd"><b>当前为「${cur.mode_label}」模式</b><div class="muted">接送安排以最新紧急通知为准，请查看通知中心并提交回执。</div></div></div>` : ""}
    ${mine ? `<div style="display:flex;justify-content:center;margin-bottom:var(--sp-4)">
      ${heroStat("ri-graduation-cap-line", mine.dismiss_time, `${esc(cls)} 放学`, `· ${esc(mine.gate)} 交接 · ${esc(mine.note || "按常规")}`)}
    </div>` : ""}
    <div class="grid g2">
    ${panel("ri-parking-box-line", "错峰共享车位", "地磁实时",
      parking.map(p => `<div class="list-item"><b>${esc(p.name)}</b>
        ${p.status === "充足" ? statusDot("online", p.status) : (p.status === "紧张" ? statusDot("warning", p.status) : statusDot("error", p.status))}
        <div class="muted">剩余 <b>${p.free ?? "—"}</b>/${p.capacity} · ${esc(p.address)}</div></div>`).join(""))}
    <div class="span2">${panel("ri-walk-line", "儿童友好通学路评分", "照明/人行道/护学岗/易涝/活跃风险 五维加权",
      commute.map(r => `<div class="list-item"><b>${esc(r.name)}</b>
        ${tag(`${RL[r.level][0]} ${r.score}分`, RL[r.level][1])}
        ${progressBar(r.score, r.score >= 80 ? `linear-gradient(90deg,${C_GREEN},${C_CYAN})` : (r.score >= 50 ? `linear-gradient(90deg,${C_ORANGE},#e8a52e)` : `linear-gradient(90deg,${C_RED},#e37318)`), "")}
        ${r.notes.length ? `<div class="muted" style="margin-top:5px">${r.notes.map(esc).join("；")}</div>` : ""}</div>`).join(""))}</div>
    </div></div>`);
  return el;
}

/* ==================== 15. 食安公示（parent） ==================== */
async function pgCanteen() {
  const b = await api("/api/canteen/board");
  const el = h(`<div>
    <div style="display:flex;justify-content:center;margin-bottom:var(--sp-4)">
      ${heroStat("ri-shield-check-line", b.food_safety_index, "食安指数", "留样合规40% + 冷链40% + 无未结食安工单20%", b.food_safety_index >= 80 ? "good" : (b.food_safety_index >= 60 ? "warn" : "bad"))}
    </div>
    ${metricRow([
      { icon: "ri-checkbox-multiple-line", num: Math.round(b.sample_compliance_rate * 100) + "%", label: "留样合规率" },
      { icon: "ri-temp-hot-line", num: b.cold_chain_ok ? "正常" : "异常", label: "冷链状态" },
      { icon: "ri-todo-line", num: b.open_food_tickets, label: "未结食安工单" },
    ])}
    <div class="grid g2">
      ${panel("ri-temp-hot-line", "留样柜温度曲线", "近24次上报 · 越限读数参与食安风险交叉印证",
        `<div class="vchart" id="ch-temp"></div>
        <div class="muted" style="margin-top:6px">红点 = 越限（≥8℃）。越限读数会与家长上报/后厨AI事件交叉印证生成食安风险。</div>`)}
      ${panel("ri-file-list-3-line", "最近留样台账", "",
        `<table class="tbl"><tr><th>日期</th><th>餐次</th><th>菜品</th><th>留样</th><th>经手人</th></tr>
        ${b.recent_samples.map(s => `<tr><td>${s.date}</td><td>${s.meal === "lunch" ? "午餐" : "早餐"}</td><td>${esc(s.dish)}</td><td>${s.weight_g}g</td><td>${esc(s.operator)}</td></tr>`).join("")}</table>`)}
    </div></div>`);
  /* 留样柜温度折线：渐变面积填充 + 阈值虚线标注 */
  mount(() => chart(el.querySelector("#ch-temp"), {
    tooltip: { trigger: "axis", valueFormatter: v => v + "℃" },
    grid: { left: 38, right: 16, top: 20, bottom: 24 },
    xAxis: { type: "category", data: b.fridge_temps.map(t => fmt(t.at)), axisLabel: { interval: 5, fontSize: 10 } },
    yAxis: { type: "value", name: "℃", max: 12 },
    series: [{
      name: "留样柜温度", type: "line", smooth: true, data: b.fridge_temps.map(t => ({
        value: t.value,
        itemStyle: t.is_anomaly ? { color: C_RED, borderColor: C_RED } : { color: C_CYAN }
      })),
      lineStyle: { color: C_CYAN },
      areaStyle: { color: { gradient: { x1: 0, y1: 0, x2: 0, y2: 1, stops: [{ offset: 0, color: "rgba(15,168,189,0.3)" }, { offset: 1, color: "rgba(15,168,189,0.02)" }] } } },
      symbolSize: 6,
      markLine: { silent: true, symbol: "none", label: { formatter: "阈值 8℃", fontSize: 10, color: C_RED },
        lineStyle: { color: C_RED, type: "dashed", width: 1.5 },
        data: [{ yAxis: 8 }] }
    }]
  }, 220));
  return el;
}

/* ==================== 16. 共享空间/预约（teacher/admin 发起） ==================== */
async function pgSpaces() {
  const canBook = ["teacher", "admin"].includes(SESSION.role);
  const [resources, emap, mine] = await Promise.all([
    api("/api/resources"), api("/api/resources/emergency-map"),
    api(`/api/resources/bookings/list?user_id=${SESSION.user_id}`)]);
  /* 预约状态色映射 */
  const bkColor = { confirmed: C_GREEN, pending: C_ORANGE, cancelled: C_RED, completed: C_BLUE };
  const el = h(`<div>
    ${panel("ri-building-2-line", "周边单位共享空间", "平急两用 · 学校侧发起预约 → 社区侧审批",
      `<table class="tbl"><tr><th>名称</th><th>类型</th><th>容量</th><th>开放时段</th><th>应急角色</th><th></th></tr>
      ${resources.map(r => `<tr><td><b>${esc(r.name)}</b><div class="muted">${esc(r.address)}</div></td>
        <td>${tag(r.category, "primary")}</td><td>${r.capacity || "—"}</td>
        <td class="muted">${r.open_hours ? Object.values(r.open_hours).map(esc).join(" / ") : "—"}</td>
        <td>${r.emergency_role ? badge(r.emergency_role === "疏散安置点" ? "避" : "援", "danger") + " " + tag(r.emergency_role, "warning", "ri-first-aid-kit-line") : "—"}</td>
        <td>${r.capacity && canBook ? btn("预约", `bookRes(${r.id},'${esc(r.name)}')`, { icon: "ri-calendar-check-line" }) : ""}</td></tr>`).join("")}</table>`)}
    <div class="grid g2">
      ${panel("ri-first-aid-kit-line", "应急资源一张图", "",
        emap.length ? `${metricRow([
          { icon: "ri-building-2-line", num: emap.length, label: "应急资源总数" },
          { icon: "ri-user-line", num: emap.reduce((s, x) => s + (x.capacity || 0), 0), label: "总容量（人）" },
        ])}
        ${emap.map(x => `<div class="list-item">${tag(x.emergency_role, "danger")} <b>${esc(x.name)}</b> <span class="muted">容量${x.capacity || "—"} · ${esc(x.contact || "")}</span></div>`).join("")}` : empty("ri-first-aid-kit-line", "暂无应急资源"))}
      ${panel("ri-calendar-todo-line", "我的预约", "",
        mine.length ? mine.map(b => `<div class="list-item" style="border-left-color:${bkColor[b.status] || C_BLUE};border-left-width:3px"><b>${b.booking_no}</b> ${b.date} ${b.start_time}-${b.end_time}
        ${tag(BKL[b.status], b.status === "confirmed" ? "success" : (b.status === "pending" ? "warning" : "default"))}
        <div class="muted">${esc(b.purpose)}</div></div>`).join("") : empty("ri-calendar-line", "暂无预约"))}
    </div></div>`);
  return el;
}
async function bookRes(id, name) {
  const date = prompt(`预约「${name}」日期（YYYY-MM-DD）：`, "2026-09-15"); if (!date) return;
  const st = prompt("开始时间（HH:MM）：", "16:00"), et = prompt("结束时间（HH:MM）：", "17:00");
  const purpose = prompt("用途：", "应急疏散演练"); if (!st || !et || !purpose) return;
  try {
    const b = await api("/api/resources/bookings", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resource_id: id, user_id: SESSION.user_id, date, start_time: st, end_time: et, purpose, attendees: 30 })
    });
    toast("预约已提交，等待社区侧审批：" + b.booking_no); go("spaces");
  } catch (e) { toast("预约失败：" + e.message, "error") }
}

/* ==================== 17. 预约审批（community） ==================== */
async function pgApprovals() {
  const [bookings, resources] = await Promise.all([
    api("/api/resources/bookings/list"), api("/api/resources")]);
  const rName = Object.fromEntries(resources.map(r => [r.id, r.name]));
  const pending = bookings.filter(b => b.status === "pending");
  const done = bookings.filter(b => b.status !== "pending").slice(0, 10);
  const el = h(`<div>
    ${divider("社区侧核对时段/容量后批准")}
    <div class="grid g2">
    ${panel("ri-time-line", `待审批预约 ${badge(pending.length, pending.length > 5 ? "danger" : "")}`, "",
      pending.length ? pending.map(b => `<div class="list-item" style="border-left-color:${C_ORANGE};border-left-width:3px">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <b>${b.booking_no}</b> · ${esc(rName[b.resource_id] || "#" + b.resource_id)}
        </div>
        <div class="muted">${b.date} ${b.start_time}-${b.end_time} · ${esc(b.purpose)} · ${b.attendees}人</div>
        <div style="margin-top:8px;display:flex;gap:8px" class="approve-btns">
          ${btn("批准", `approveBk('${b.booking_no}','confirmed',this)`, { icon: "ri-check-line" })}
          ${btn("驳回", `approveBk('${b.booking_no}','cancelled',this)`, { theme: "danger", variant: "outline", icon: "ri-close-line" })}
        </div></div>`).join("") : empty("ri-checkbox-circle-line", "暂无待审批预约"))}
    ${panel("ri-history-line", "已处理记录", "",
      done.length ? done.map(b => `<div class="list-item" style="border-left-color:${b.status === "confirmed" ? C_GREEN : C_RED};border-left-width:3px"><b>${b.booking_no}</b> · ${esc(rName[b.resource_id] || "")}
        ${tag(BKL[b.status], b.status === "confirmed" ? "success" : "default")}
        <div class="muted">${b.date} ${b.start_time}-${b.end_time} · ${esc(b.purpose)}</div></div>`).join("") : empty("ri-history-line", "暂无记录"))}
    </div></div>`);
  return el;
}
async function approveBk(no, to, btnEl) {
  /* 审批按钮确认状态 */
  const btns = btnEl.closest(".approve-btns");
  if (btns) {
    btns.innerHTML = `<span style="font-size:13px;color:${to === "confirmed" ? C_GREEN : C_RED};animation:fadein .3s ease"><i class="${to === "confirmed" ? "ri-checkbox-circle-line" : "ri-close-circle-line"}"></i> ${to === "confirmed" ? "已批准" : "已驳回"}，正在同步…</span>`;
  }
  try {
    await api(`/api/resources/bookings/${no}/status?status=${to}&operator_id=${SESSION.user_id}`, { method: "PATCH" });
    toast(to === "confirmed" ? "已批准" : "已驳回"); go("approvals");
  } catch (e) { toast("操作失败：" + e.message, "error") }
}

/* ==================== 18. 随手拍（parent/teacher） ==================== */
async function pgReport() {
  const mine = (await api("/api/incidents?limit=50")).filter(i => i.reporter_id === SESSION.user_id);
  const stColor = { reported: C_BLUE, dispatched: C_CYAN, processing: C_ORANGE, resolved: C_GREEN, closed: "var(--ink-3)" };
  const el = h(`<div class="grid g2">
    ${panel("ri-camera-line", "随手拍上报", "AI自动分类→派单，并作为citizen模态参与风险交叉印证",
      `<div class="form-row"><label>问题描述</label>
      <textarea id="rp-desc" class="native" rows="4" placeholder="例：东门下凹路段积水很深，孩子过不去 / 食堂饭菜有异物 / 六年级1班课桌摇晃…"></textarea></div>
      <div class="form-row"><label>位置</label>
      <select id="rp-loc" class="native"><option>东门</option><option>东门下凹路段</option><option>南门</option><option>京开辅路口</option><option>食堂后厨</option><option>翻新教室(六年级1班)</option><option>六年级教学楼</option><option>操场</option></select></div>
      <div style="display:flex;align-items:center;gap:6px;margin:var(--sp-2) 0;color:var(--ink-3);font-size:var(--fs-xs)">
        <i class="ri-image-add-line"></i> 可在此处拖拽添加现场照片（功能开发中）
      </div>
      ${btn("提交上报", "submitReport()", { icon: "ri-send-plane-fill", size: "m" })}
      <div class="muted" id="rp-msg" style="margin-top:8px"></div>`)}
    ${panel("ri-history-line", "我的上报", "",
      mine.length ? `<div class="report-timeline">${mine.map(i => `<div class="list-item" style="border-left-color:${stColor[i.status] || C_BLUE};border-left-width:3px">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          <b>${i.ticket_no}</b> ${tag(CATL[i.category], "primary")}
          ${tag(STL[i.status], i.status === "resolved" || i.status === "closed" ? "success" : "warning")}
          <span class="muted" style="margin-left:auto"><i class="ri-time-line"></i> ${fmt(i.created_at)}</span>
        </div>
        <div class="muted" style="margin-top:3px">${esc(i.description.slice(0, 80))}${i.description.length > 80 ? "…" : ""} → ${esc(i.assignee || "")}</div></div>`).join("")}</div>` : empty("ri-camera-line", "暂无上报记录"))}
  </div>`);
  return el;
}
async function submitReport() {
  const desc = document.getElementById("rp-desc").value.trim(), loc = document.getElementById("rp-loc").value;
  const msg = document.getElementById("rp-msg");
  if (desc.length < 2) { msg.textContent = "请填写描述"; return }
  try {
    const r = await api("/api/incidents", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reporter_id: SESSION.user_id, description: desc, location: loc })
    });
    msg.innerHTML = `<i class="ri-checkbox-circle-line" style="color:#2ba471"></i> 工单 <b>${r.ticket_no}</b>：AI识别[${CATL[r.category]}]（置信度${r.confidence}），已派 ${esc(r.assignee)}`;
    document.getElementById("rp-desc").value = "";
  } catch (e) { msg.textContent = "失败：" + e.message }
}
