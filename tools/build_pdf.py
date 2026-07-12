# -*- coding: utf-8 -*-
"""生成《红门哨兵 · 分角色页面功能讲解》PDF（v4）

读取 docs/screenshots/ 下截图，配中文讲解文字，输出 docs/红门哨兵_分角色页面讲解.pdf
用途：供专家评审（不含代码细节，讲清每页给谁看、解决什么问题、背后什么技术）。
"""
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
OUT_PDF = ROOT / "docs" / "红门哨兵_分角色页面讲解.pdf"

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm

# ---------- 中文字体 ----------
def register_fonts():
    candidates = [
        (r"C:\Windows\Fonts\msyh.ttc", 0),      # 微软雅黑
        (r"C:\Windows\Fonts\msyhbd.ttc", 0),
        (r"C:\Windows\Fonts\simhei.ttf", None), # 黑体
        (r"C:\Windows\Fonts\simsun.ttc", 0),
    ]
    for path, idx in candidates:
        if Path(path).exists():
            try:
                if idx is None:
                    pdfmetrics.registerFont(TTFont("CN", path))
                else:
                    pdfmetrics.registerFont(TTFont("CN", path, subfontIndex=idx))
                return "CN"
            except Exception:
                continue
    raise RuntimeError("未找到可用中文字体")

FONT = register_fonts()

# ---------- 讲解文案 ----------

COVER_TITLE = "红门哨兵"
COVER_SUB = "大兴区西红门实验二小 · 校园智能体（平急结合）"
COVER_LINES = [
    "赛道三：城市管理（单项）",
    "",
    "本文档按登录角色逐页展示系统全部页面，并附功能与技术讲解，",
    "供专家评审提出修改意见。当前为 v4 演示版本，功能与界面均可调整。",
    "",
    "系统定位：区级城运中心（一云两平台）与镇级智慧社区之间的",
    "\u201c校园及周边100米\u201d空白地带，以学校为边缘节点的平急结合校园智能体。",
    "",
    "急时：安全哨兵 —— IoT感知+边缘AI视频 → 本体多模态融合 → 预案引擎/图算法 → 分级通知与工单处置",
    "平时：教联体数字底座 —— 健康档案 / AI体测 / 选修课推荐 / 请假台账 / 用餐日历 / 年检公示 / 场馆口碑",
]

ARCH_TITLE = "总体架构与角色权限设计（v4）"
ARCH_LINES = [
    "■ 急时线：四层架构",
    "  感知层：13台IoT传感器（水位/噪音·含楼梯间/微气象/留样柜温度/甲醛TVOC/双停车场地磁）+ 边缘AI相机。",
    "  视频帧在边缘侧推理后即时丢弃，只保留事件类型与SHA-256快照哈希——无人脸、无原图，",
    "  对齐《未成年人网络保护条例》对儿童数据的要求。",
    "  认知层：轻量本体论框架（类层级+处置知识库+推理规则），要求至少2类独立模态交叉印证才确认风险，",
    "  防止单一来源误报；每条风险附可解释推理链。两个有明确论证的例外：地震官方预警高可信单源直通；",
    "  缺勤聚集（R-ILLNESS）以\u201c3份独立家长病假单\u201d等价多源。新增双模态规则 R-STAIR：",
    "  楼梯间视觉密度+噪音≥75dB 交叉印证 → 拥挤风险 → 分层错时下楼预案。",
    "  决策层：预案引擎将北京市教委预警响应规则数字化（预警类型×级别→运行模式+动作清单，只升不降防抖动）；",
    "  校园路网 Dijkstra 风险加权，实时计算疏散路线与儿童友好通学路评分。",
    "  处置层：工单状态机 + 分级分众通知（定向到人、回执可查、紧急15分钟未读升级电话补呼）。",
    "",
    "■ 平时线：教联体数字底座（v4 新增，与急时线同底座）",
    "  健康档案：WS/T 586 BMI分性别界值 + 视力连续下滑判定 + 膳食指南规则引擎生成营养建议，",
    "  强制附\u201c非医疗诊断\u201d声明；只与自己比、不排名。AI体测：视频→姿态关键点计数，只存成绩不存视频。",
    "  选修课推荐：六因子可解释打分（体测弱项权重最高/健康趋势/成绩扬长补短/兴趣/校外同项目排除/时段冲突），",
    "  每条推荐附理由、报名时快照留痕；探索推荐防信息茧房；家长可一键关闭个性化。",
    "  请假台账：病假症状标签→同班3天内同症状≥3例自动进多模态融合生成缺勤聚集预警（平时数据驱动急时预警）；",
    "  班主任首次能看到每生本月/学期请假统计。用餐日历：按月勾选→后厨备餐台账→月末后付费账单（无余额无饭卡），",
    "  请假获批只提示重叠用餐日、不自动动钱。年检公示墙：7门类效期规则引擎自动提醒超期/临期/不合格；",
    "  课桌椅按GB/T 3976联动体检身高，只公示比例不公示身高。场馆口碑：教师带班点评，差评自动置顶规避提示。",
    "",
    "■ 慎做清单（主动规避）：不做人脸识别、不做情绪识别、不做成绩/体测排名公示、校园感知不进家庭。",
    "",
    "■ 四个角色与权限边界（本次评审重点）",
    "  赵校长（admin）＝学校安全工作第一责任人（《中小学校岗位安全工作指南》），即系统管理员：",
    "    指挥大屏 / 预案矩阵 / 工单管理 / 资产管理（归口校长，教师端403）/ 年检公示 / 共享空间。",
    "  李老师（六年级1班班主任）：通知中心 / 请假审批·缺勤统计·备餐台账 / 共享空间预约 / 场馆点评 / 安全公示 / 随手拍。",
    "  王女士（六年级1班家长）：孩子空间（健康/体测/成绩/兴趣/校外班）/ 选修课 / 请假 / 用餐日历 /",
    "    通知回执 / 安全出行 / 食安公示 / 随手拍。",
    "  张主任（社区居委会·红门管家）：工单处置台 / 风险事件 / 预约审批——只审批不发起（接口层403强制）。",
    "",
    "■ 学生为何没有账号：一人一档、不一人一号",
    "  小学生无手机，班级一体机暂无采购预算，故不设学生账号；学生建\u201c档\u201d不建\u201c号\u201d——",
    "  档案挂在家长账号下内嵌查看，三级守卫（本家长/同班班主任/校长），跨家长访问403。",
    "  种子数据中同班同学各挂独立家长账号，隐私边界在数据层真实成立，而非仅前端隐藏。",
    "",
    "■ 界面配色",
    "  参照\u201c一网统管\u201d城运中心大屏（深空蓝+青色高亮，校长指挥端）与政务服务门户",
    "  （政务蓝浅色，家长/教师/社区服务端）双主题，按角色自动切换。",
]

# 每张截图的讲解：文件名 → (标题, 正文行列表)
CAPTIONS = {
    "00_login": ("登录页 · 点选身份进入", [
        "登录页只展示四个演示身份卡片（姓名+角色定位），点\u201c进入\u201d即登录，不展示任何口令。",
        "四个身份覆盖\u201c学校-家庭-社区\u201d三方协同：校长、班主任、家长、社区管家。",
        "页脚注明：学生实行\u201c一人一档、不一人一号\u201d，档案由家长账号内嵌查看——权限设计而非功能缺失。",
        "演示人物统一锚定六年级1班——课桌成色、甲醛监测、健康档案、请假剧情均发生在该班，故事线闭环。",
    ]),
    "admin_1_dashboard": ("赵校长 · 指挥大屏（常态）", [
        "校长是学校安全第一责任人，大屏采用城运中心深色主题。四个KPI：活跃风险数、异常/在网IoT设备、",
        "累计工单（按来源分：随手拍/AI视频/传感器/扫码报修）、当前校园运行模式。",
        "左上：融合风险事件列表（点击展开可解释推理链）；右上：场景注入器（演示核心，一键回放典型事件，",
        "v4场景去日期化并新增\u201c缺勤聚集\u201d\u201c楼梯间拥挤\u201d）。左下：IoT实时遥测；右下：Dijkstra实时疏散路线。",
    ]),
    "admin_2_matrix": ("赵校长 · 预案矩阵", [
        "北京市教委预警响应规则的数字化：预警类型×级别 → 运行模式 + 动作清单，全量公开、每次切换留审计痕。",
        "标\u201c自动\u201d的动作由智能体直接执行（如发送分级通知、切换接送方案），其余标注责任人待确认。",
        "运行模式单调升级（正常→错峰→室内→居家→疏散），防止预警抖动导致反复切换。",
    ]),
    "admin_3_workbench": ("赵校长 · 工单管理", [
        "全部工单的状态机视图：上报→派单→处理→解决→归档。每单显示AI分类结果、派单对象、优先级、来源。",
        "来源标签体现多模态：随手拍（家长/教师）、AI视频（边缘相机）、传感器（IoT越限）、扫码报修（资产）。",
        "AI分类器按关键词+区域自动派单：积水→镇市政维修组P1、食安→食堂负责人+区市场监管所P1、",
        "甲醛→总务处+施工方P1，体现\u201c居民-物业-居委会\u201d式三方协同在校园场景的映射。",
    ]),
    "admin_4_assets": ("赵校长 · 资产管理（v4：归口校长，教师端不可见）", [
        "资产台账是管理动作（采购/淘汰决策），归口安全第一责任人：教师访问台账接口返回403，",
        "但扫码报修任何角色可用——发现坏损即报，报修与管理解耦。",
        "台账精确到班：AS-G6C1-DESK（六年级1班2017年购置，成色2/5）单列，不以个案推断全年级；",
        "上方按年级公示平均成色，最差年级标红。超龄或成色≤2的资产自动标\u201c建议淘汰\u201d，",
        "与年检页的淘汰清单联动（课桌椅8年/体育器械6年门类年限规则引擎）。",
        "翻新工程资产联动甲醛/TVOC传感器持续公示。",
    ]),
    "admin_5_inspections": ("赵校长 · 年检公示墙 + 淘汰清单（v4新增）", [
        "每年一次的安全检查数字化公示：甲醛/直饮水/消防器材/教室照明/体育器械/急救箱/课桌椅 七门类，",
        "每条带检化验报告编号可核验。效期规则引擎自动提醒：已超期（红）/30天内临期（橙）/不合格（红）。",
        "课桌椅身高匹配：GB/T 3976型号身高区间 × 体检档案身高联查，只公示匹配比例与\u201cX同学建议2号桌\u201d，",
        "不公示身高数值——隐私设计。右侧资产超龄淘汰清单由规则引擎自动生成，附处置建议。",
    ]),
    "admin_6_spaces": ("赵校长 · 共享空间（平急两用）", [
        "小学使用周边单位空余空间（文体中心/党群服务中心/消防站/错峰车位等）。",
        "每处资源标注\u201c应急角色\u201d（避难点/安置点/医疗点/救援驻点）——平时是预约资源，急时一键转应急资产，",
        "即城市管理正式术语\u201c平急两用\u201d。校长与教师可发起预约，社区侧审批。",
        "\u201c应急资源一张图\u201d：应急状态下各点位角色、容量、联系方式一屏可见。",
    ]),
    "admin_chat": ("赵校长 · 智能助手", [
        "对话入口悬浮于所有页面。意图识别（13类意图）+ 角色权限矩阵：同一句话不同角色得到不同能力。",
        "查风险/查预案时直接返回实时数据（活跃风险列表、当前模式），并自动跳转到对应页面。",
    ]),
    "teacher_1_inbox": ("李老师（班主任）· 通知中心", [
        "教师收到的通知与家长同源但受众不同（定向投递）。应急通知中标注教师的动作清单",
        "（如\u201c组织学生到室内\u201d），并需回执确认，学校端可实时查看各班响应情况。",
    ]),
    "teacher_2_leaveadmin": ("李老师（班主任）· 请假审批·缺勤统计·备餐台账（v4新增）", [
        "调研发现：请假散落在微信聊天里，班主任说不清每个孩子这学期请了几天假。本页三合一：",
        "①待审批请假：家长提交的病假/事假（病假必须勾症状标签），一键批准/退回；",
        "  批准病假时若与用餐日历重叠，系统弹出提示但只建议、不自动动钱。",
        "②缺勤统计：首次能看到每个孩子本月/本学期请假天数（病假/事假分列）。",
        "③今日备餐台账：联动家长的用餐日历，按班聚合人数供后厨备餐。",
        "顶部症状监测横幅：近3天同班同症状≥3例自动预警（脱敏聚合，不公开个人）——",
        "平时的请假台账数据直接驱动急时的缺勤聚集风险融合（R-ILLNESS规则）。",
    ]),
    "teacher_3_spaces": ("李老师（班主任）· 共享空间预约", [
        "教师是预约的发起方：选定资源→提交日期时段用途→状态为\u201c待审批\u201d，由社区侧张主任批准。",
        "接口层有冲突检测（同资源同日时段重叠返回409）与容量校验（超容量拒绝）。",
    ]),
    "teacher_4_venues": ("李老师（班主任）· 场馆点评（v4新增）", [
        "带班老师外出场馆后写点评（仅教师/校长可写，家长403），后来的老师订场前先看口碑榜。",
        "评分≤2星自动置顶为\u201c差评规避提示\u201d——例如创客空间\u201c设备一半故障、讲解员照本宣科\u201d，",
        "帮助后续班级避坑。对应教联体\u201c馆校协同\u201d：不只对接资源，还沉淀使用经验。",
    ]),
    "teacher_5_inspections": ("李老师（班主任）· 安全公示（公示视角）", [
        "教师看到与家长相同的年检公示墙（七门类+效期提醒+课桌椅匹配率），但没有淘汰清单等管理视图——",
        "公示人人可见，管理归口校长。",
    ]),
    "teacher_6_report": ("李老师（班主任）· 随手拍", [
        "与家长随手拍同一入口，教师上报同样进入AI分类派单与多模态融合。",
    ]),
    "parent_1_child": ("王女士（家长）· 孩子空间（v4核心新增：一人一档不一人一号）", [
        "小明的完整成长档案内嵌在家长账号下：",
        "①每学期健康档案：身高/体重/视力/龋齿纵向对比+趋势图；BMI按WS/T 586分性别界值判定（小明超重），",
        "  视力三学期连降触发提醒。②健康提示由规则引擎生成，强制附\u201c非医疗诊断\u201d声明，超重→有氧+控糖建议，",
        "  附建议关注的维生素/矿物质种类。③AI体测：跳绳60分弱项标红并给锻炼处方；家长可上传动作视频，",
        "  边缘AI骨架关键点计数，原始视频推理后即丢弃。④成绩只做自己纵向对比，不显示班级排名。",
        "⑤校外兴趣班登记：登记后选修课不再重复推荐同项目。",
    ]),
    "parent_2_courses": ("王女士（家长）· 选修课（v4新增：AI可解释推荐）", [
        "每个孩子看到的选修课排序不同：六因子可解释打分——体测弱项+40（权重最高，跳绳弱→花样跳绳置顶）、",
        "健康趋势±15（视力下滑→户外加分/屏幕类减分）、成绩扬长补短+20、兴趣+25、校外同项目排除",
        "（校外已学篮球→校园篮球标灰，但只排除同项目不排除整个体育类）、时段冲突硬约束。",
        "每条推荐列出全部理由；\u201c探索推荐\u201d从未接触的类别中选一门防信息茧房；",
        "家长可一键关闭个性化（目录原序返回）；报名时推荐理由做快照留痕，可追溯\u201c当时为什么推荐\u201d。",
    ]),
    "parent_3_leave": ("王女士（家长）· 请假（v4新增）", [
        "替代微信里喊一声的请假：选日期范围（按工作日计天数）、病假必须勾症状标签（发热/咳嗽/呕吐…）。",
        "症状只用于同班聚集性缺勤预警（3天内同症状≥3例触发校医排查），脱敏聚合、不公开个人——",
        "页面明确告知家长数据用途。右侧请假记录可见审批状态与审批人。",
    ]),
    "parent_4_meals": ("王女士（家长）· 用餐日历（v4新增）", [
        "调研发现：饭费靠微信群接龙报日子，学校没有台账。本页把它管起来：",
        "按月日历勾选在校用餐日（周末置灰不可选），保存后后厨按日备餐、班主任可见台账。",
        "右侧账单预览：天数×单价，月末按实际勾选出账、银行卡后付费——不设余额、不用饭卡。",
        "请假获批若与用餐日重叠，系统只提示、由家长自行调整，不自动动钱。",
    ]),
    "parent_5_inbox": ("王女士（家长）· 通知中心", [
        "替代微信群的三个硬能力：①定向到人（按角色+班级投递，不刷屏）；②回执可查（紧急通知需点",
        "\u201c我已知晓\u201d，学校端能看到谁没读）；③紧急通知15分钟未读自动升级电话补呼。",
        "v4新增\u201c家庭安全提示\u201d类通知（火/刀具/窗台）——只推家长，校园AI不进家庭。",
    ]),
    "parent_6_travel": ("王女士（家长）· 安全出行", [
        "①今日接送卡片：本班放学时间与交接门（错峰接送，减少校门口瞬时聚集）；",
        "②错峰共享车位：周边两处停车场地磁传感器实时空位，接送高峰对家长开放；",
        "③儿童友好通学路评分：照明25+人行道25+护学岗20+无易涝15+无活跃风险15 五维加权，",
        "  给出推荐/注意/避开三档，应急时随风险实时改变。",
    ]),
    "parent_7_canteen": ("王女士（家长）· 食安公示", [
        "食堂透明化闭环：①食安指数=留样合规40%+冷链40%+无未结食安工单20%；②留样合规率按GB 31654",
        "（每餐每菜125g冷藏48小时）计算；③留样柜温度IoT连续监测（0-8℃），越限标红并与家长上报、",
        "后厨AI事件交叉印证生成食安风险。台账+曲线全部对家长公开。",
    ]),
    "parent_8_report": ("王女士（家长）· 随手拍", [
        "家长上报问题，AI自动分类→自动派单，右侧跟踪本人工单进度。",
        "关键设计：每条上报作为citizen模态进入多模态融合，与传感器/视频交叉印证——",
        "例：家长报\u201c东门积水\u201d+水位计越限 → 两类独立模态确认，风险升级并自动触发预案。",
    ]),
    "parent_chat": ("王女士（家长）· 智能助手", [
        "v4家长新增意图：问\u201c孩子健康档案\u201d\u201c选修课推荐\u201d\u201c怎么请假\u201d\u201c这个月饭费\u201d均可识别并跳转对应页面，",
        "回复带边界声明（如健康回复注明非医疗诊断）。同一助手，角色不同能力不同。",
    ]),
    "community_1_workbench": ("张主任（社区·红门管家）· 工单处置台", [
        "社区侧是处置主力：镇市政维修组、红门管家志愿队等对应工单在此流转（开始处理→标记解决→归档）。",
        "对应\u201c居民-物业-居委会三方协同\u201d：学校上报、社区处置、平台留痕。",
    ]),
    "community_2_hazards": ("张主任（社区·红门管家）· 风险事件", [
        "社区侧可见全部活跃风险及其处置建议与推理链，可推进风险状态（开始处置→标记解除）。",
        "推理链让非技术人员也能看懂\u201c为什么系统认为有风险\u201d：哪几路信号、什么阈值、什么规则命中。",
    ]),
    "community_3_approvals": ("张主任（社区·红门管家）· 预约审批", [
        "权限设计要点：张主任作为资源方只审批、不发起预约（接口层403强制，非仅前端隐藏按钮）。",
        "左侧待审批列表（批准/驳回），右侧已处理记录。学校侧发起→社区侧审批的单向流，",
        "对应真实世界中\u201c周边单位空间归属方\u201d的管理边界。",
    ]),
    "emergency_1_admin_dashboard": ("应急对比 · 校长指挥大屏（注入\u201c放学高峰暴雨\u201d场景后）", [
        "场景注入器回放\u201c放学高峰遭遇暴雨橙色预警\u201d情景（v4去日期化：不锚定具体日期，聚焦最危险的时段组合；",
        "走真实数据入口，非后门演示）：官方橙警接入 → 预案引擎自动切\u201c室内避险·延迟放学\u201d（顶栏红闪）；",
        "水位计越限（>15cm）+ 边缘AI积水事件 + 家长上报 → 三类独立模态交叉印证，",
        "本体推理确认\u201c积水内涝@东门下凹路段\u201d severity 4（紧急），推理链完整可查（图中已展开）；",
        "疏散路线自动绕开风险区域，全员紧急通知自动发出。",
    ]),
    "emergency_2_parent_inbox": ("应急对比 · 家长通知中心", [
        "家长收到紧急通知：预案切换通知（含动作清单：谁自动执行、谁待确认）与内涝风险通知。",
        "紧急通知要求回执，15分钟未读将进入电话补呼清单——保证暴雨天\u201c每一位家长都被触达\u201d。",
    ]),
    "emergency_3_parent_travel": ("应急对比 · 家长安全出行", [
        "应急模式下出行页顶部出现红色横幅\u201c接送以最新紧急通知为准\u201d；",
        "通学路评分实时变化：途经东门下凹路段的路线因\u201c活跃风险\u201d维度扣分被标红\u201c避开\u201d。",
    ]),
    "emergency_4_teacher_illness_watch": ("应急对比 · 班主任缺勤聚集预警（注入\u201c缺勤聚集\u201d场景后）", [
        "平时数据驱动急时预警的代表场景：3位家长各自提交\u201c发热\u201d病假 → 请假台账症状聚合 →",
        "R-ILLNESS规则（3份独立病假单等价多源交叉印证）→ 生成\u201c缺勤聚集\u201d风险 → 校医排查/晨午检/",
        "通风消毒预案。班主任页面顶部横幅直接显示\u201c某班·发热×3例\u201d，与指挥大屏风险事件联动。",
        "这是传染病早期发现的低成本数字哨点：不加装任何设备，用请假流程自然沉淀的数据完成监测。",
    ]),
}

# 章节划分：(章节标题, 截图前缀列表)
SECTIONS = [
    ("一、登录与身份", ["00_login"]),
    ("二、赵校长（校长·安全第一责任人 = 系统管理员）",
     ["admin_1_dashboard", "admin_2_matrix", "admin_3_workbench",
      "admin_4_assets", "admin_5_inspections", "admin_6_spaces", "admin_chat"]),
    ("三、李老师（六年级1班班主任）",
     ["teacher_1_inbox", "teacher_2_leaveadmin", "teacher_3_spaces",
      "teacher_4_venues", "teacher_5_inspections", "teacher_6_report"]),
    ("四、王女士（六年级1班家长·内嵌孩子空间）",
     ["parent_1_child", "parent_2_courses", "parent_3_leave", "parent_4_meals",
      "parent_5_inbox", "parent_6_travel", "parent_7_canteen", "parent_8_report", "parent_chat"]),
    ("五、张主任（社区居委会·红门管家）",
     ["community_1_workbench", "community_2_hazards", "community_3_approvals"]),
    ("六、应急状态对比（场景注入后）",
     ["emergency_1_admin_dashboard", "emergency_2_parent_inbox",
      "emergency_3_parent_travel", "emergency_4_teacher_illness_watch"]),
]


def draw_wrapped(c, text, x, y, max_w, size=10.5, leading=16, color=(0.16, 0.22, 0.33)):
    """逐字符折行绘制中文文本，返回结束后的y"""
    c.setFont(FONT, size)
    c.setFillColorRGB(*color)
    line = ""
    for ch in text:
        if pdfmetrics.stringWidth(line + ch, FONT, size) > max_w:
            c.drawString(x, y, line)
            y -= leading
            line = ch
        else:
            line += ch
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def cover(c):
    c.setFillColorRGB(0.04, 0.09, 0.19)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont(FONT, 40)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 150, COVER_TITLE)
    c.setFont(FONT, 15)
    c.setFillColorRGB(0.62, 0.72, 0.87)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 185, COVER_SUB)
    c.setFillColorRGB(0.16, 0.82, 0.91)
    c.setFont(FONT, 12)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 215, "分角色页面功能讲解 · 专家评审版（v4）")
    y = PAGE_H - 300
    c.setFont(FONT, 11.5)
    for line in COVER_LINES:
        c.setFillColorRGB(0.82, 0.87, 0.95)
        c.drawCentredString(PAGE_W / 2, y, line)
        y -= 22
    c.showPage()


def arch_page(c):
    c.setFillColorRGB(0.05, 0.16, 0.32)
    c.setFont(FONT, 18)
    c.drawString(MARGIN, PAGE_H - MARGIN - 10, ARCH_TITLE)
    c.setStrokeColorRGB(0.06, 0.66, 0.74)
    c.setLineWidth(2)
    c.line(MARGIN, PAGE_H - MARGIN - 20, MARGIN + 70 * mm, PAGE_H - MARGIN - 20)
    y = PAGE_H - MARGIN - 45
    for line in ARCH_LINES:
        if not line:
            y -= 8
            continue
        size = 11 if line.startswith("■") else 9.8
        color = (0.05, 0.16, 0.32) if line.startswith("■") else (0.22, 0.28, 0.38)
        y = draw_wrapped(c, line, MARGIN, y, PAGE_W - 2 * MARGIN, size=size, leading=15.5, color=color)
        if y < MARGIN + 30:
            c.showPage()
            y = PAGE_H - MARGIN - 20
    c.showPage()


def section_divider(c, title):
    c.setFillColorRGB(0.95, 0.97, 1.0)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColorRGB(0.05, 0.16, 0.32)
    c.setFont(FONT, 24)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 10, title)
    c.setStrokeColorRGB(0.06, 0.66, 0.74)
    c.setLineWidth(2.5)
    c.line(PAGE_W / 2 - 60 * mm, PAGE_H / 2 - 12, PAGE_W / 2 + 60 * mm, PAGE_H / 2 - 12)
    c.showPage()


def shot_page(c, key):
    img_path = SHOTS / f"{key}.png"
    title, lines = CAPTIONS.get(key, (key, []))
    # 标题
    c.setFillColorRGB(0.05, 0.16, 0.32)
    c.setFont(FONT, 14.5)
    c.drawString(MARGIN, PAGE_H - MARGIN - 8, title)
    c.setStrokeColorRGB(0.06, 0.66, 0.74)
    c.setLineWidth(1.5)
    c.line(MARGIN, PAGE_H - MARGIN - 16, PAGE_W - MARGIN, PAGE_H - MARGIN - 16)
    # 讲解文字
    y = PAGE_H - MARGIN - 34
    for line in lines:
        y = draw_wrapped(c, line, MARGIN, y, PAGE_W - 2 * MARGIN, size=9.8, leading=15)
    y -= 6
    # 截图（等比缩放放入剩余区域；截图可能是长页，必要时按宽度缩放并截断显示上部）
    if img_path.exists():
        img = Image.open(img_path)
        iw, ih = img.size
        avail_w = PAGE_W - 2 * MARGIN
        avail_h = y - MARGIN
        scale = avail_w / iw
        draw_h = ih * scale
        if draw_h > avail_h:
            # 只展示图像上部（页面主要内容区），裁切
            crop_h = int(avail_h / scale)
            img = img.crop((0, 0, iw, crop_h))
            tmp = img_path.with_suffix(".crop.png")
            img.save(tmp)
            c.drawImage(str(tmp), MARGIN, y - avail_h, width=avail_w, height=avail_h)
            tmp.unlink(missing_ok=True)
            c.setFont(FONT, 8)
            c.setFillColorRGB(0.55, 0.6, 0.7)
            c.drawRightString(PAGE_W - MARGIN, MARGIN - 6, "（页面较长，此处展示上半部分）")
        else:
            c.drawImage(str(img_path), MARGIN, y - draw_h, width=avail_w, height=draw_h)
    else:
        c.setFont(FONT, 11)
        c.setFillColorRGB(0.8, 0.3, 0.3)
        c.drawString(MARGIN, y - 30, f"[缺少截图 {key}.png]")
    c.showPage()


def main():
    c = canvas.Canvas(str(OUT_PDF), pagesize=A4)
    c.setTitle("红门哨兵 · 分角色页面功能讲解")
    cover(c)
    arch_page(c)
    for sec_title, keys in SECTIONS:
        section_divider(c, sec_title)
        for k in keys:
            shot_page(c, k)
    c.save()
    print(f"PDF 已生成：{OUT_PDF}")


if __name__ == "__main__":
    main()
