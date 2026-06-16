"""建模竞赛日历 — 全年竞赛时间轴"""

from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Competition:
    """竞赛信息"""
    id: str
    name: str
    name_en: str
    organizer: str
    level: str  # 国家级/省级/国际级
    month: int  # 大致月份
    duration_hours: int  # 比赛时长
    team_size: str  # 队伍规模
    language: str  # 中文/英文
    description: str
    difficulty: str  # 初级/中级/高级
    prizes: str = ""
    website: str = ""
    tips: List[str] = field(default_factory=list)


COMPETITIONS: List[Competition] = [
    Competition(
        id="cumcm",
        name="全国大学生数学建模竞赛（国赛）",
        name_en="CUMCM",
        organizer="中国工业与应用数学学会",
        level="国家级",
        month=9,
        duration_hours=72,
        team_size="3人",
        language="中文",
        description="国内规模最大的数学建模竞赛，每年9月举行，分A/B/C三题。",
        difficulty="高级",
        prizes="国家一/二/三等奖",
        tips=["A题偏连续建模，B题偏离散建模，C题偏数据分析", "论文格式要求严格，注意排版", "72小时赛程，合理分配时间"],
    ),
    Competition(
        id="mcm_icm",
        name="美国大学生数学建模竞赛（美赛）",
        name_en="MCM/ICM",
        organizer="COMAP",
        level="国际级",
        month=2,
        duration_hours=96,
        team_size="3人",
        language="英文",
        description="国际知名数学建模竞赛，分MCM（数学建模）和ICM（交叉学科建模）。",
        difficulty="高级",
        prizes="Outstanding/Finalist/Meritorious/Honorable Mention",
        tips=["英文论文写作是关键", "MCM偏数学，ICM偏综合", "注意引用格式和图表质量"],
    ),
    Competition(
        id="huashu",
        name="华数杯数学建模竞赛",
        name_en="HuashuCup",
        organizer="华中科技大学",
        level="省级",
        month=5,
        duration_hours=72,
        team_size="3人",
        language="中文",
        description="华中地区知名建模竞赛，难度适中，适合练手。",
        difficulty="中级",
        tips=["适合新手练手", "题目类型与国赛类似"],
    ),
    Competition(
        id="huawei",
        name="华为杯数学建模竞赛",
        name_en="Huawei Cup",
        organizer="华为",
        level="国家级",
        month=11,
        duration_hours=72,
        team_size="3人",
        language="中文",
        description="华为赞助的建模竞赛，题目偏工程应用。",
        difficulty="高级",
        prizes="一/二/三等奖 + 华为实习机会",
        tips=["题目偏工程实践", "可能涉及通信/网络相关知识"],
    ),
    Competition(
        id="mayday",
        name="五一数学建模竞赛",
        name_en="May Day MCM",
        organizer="中国优选法统筹法与经济数学研究会",
        level="省级",
        month=5,
        duration_hours=72,
        team_size="3人",
        language="中文",
        description="每年五一期间举行，难度适中。",
        difficulty="中级",
        tips=["适合积累经验", "时间安排在五一假期"],
    ),
    Competition(
        id="mathorcup",
        name="MathorCup 高校数学建模挑战赛",
        name_en="MathorCup",
        organizer="中国优选法统筹法与经济数学研究会",
        level="国家级",
        month=4,
        duration_hours=120,
        team_size="3人",
        language="中文",
        description="赛程较长（5天），有充足时间深入研究。",
        difficulty="中级",
        tips=["赛程长，注意节奏", "可以深入研究问题"],
    ),
    Competition(
        id="electrician",
        name="电工杯数学建模竞赛",
        name_en="Electrician Cup",
        organizer="中国电机工程学会",
        level="国家级",
        month=6,
        duration_hours=72,
        team_size="3人",
        language="中文",
        description="偏电力系统和电气工程方向的建模竞赛。",
        difficulty="高级",
        tips=["需要电力系统背景知识", "题目偏工程应用"],
    ),
    Competition(
        id="network",
        name="数维杯大学生数学建模竞赛",
        name_en="Network Cup",
        organizer="内蒙古自治区数学学会",
        level="省级",
        month=4,
        duration_hours=72,
        team_size="3人",
        language="中文",
        description="适合新手入门的建模竞赛。",
        difficulty="初级",
        tips=["适合新手练手", "题目难度较低"],
    ),
]


class CompetitionCalendar:
    """竞赛日历"""

    def __init__(self):
        self.competitions = {c.id: c for c in COMPETITIONS}

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有竞赛"""
        return [
            {
                "id": c.id,
                "name": c.name,
                "name_en": c.name_en,
                "organizer": c.organizer,
                "level": c.level,
                "month": c.month,
                "duration_hours": c.duration_hours,
                "team_size": c.team_size,
                "language": c.language,
                "difficulty": c.difficulty,
                "description": c.description,
            }
            for c in sorted(COMPETITIONS, key=lambda x: x.month)
        ]

    def get_competition(self, comp_id: str) -> Dict[str, Any] | None:
        """获取竞赛详情"""
        c = self.competitions.get(comp_id)
        if not c:
            return None
        return {
            "id": c.id,
            "name": c.name,
            "name_en": c.name_en,
            "organizer": c.organizer,
            "level": c.level,
            "month": c.month,
            "duration_hours": c.duration_hours,
            "team_size": c.team_size,
            "language": c.language,
            "difficulty": c.difficulty,
            "description": c.description,
            "prizes": c.prizes,
            "website": c.website,
            "tips": c.tips,
        }

    def get_upcoming(self, current_month: int = None) -> List[Dict[str, Any]]:
        """获取即将开始的竞赛"""
        if current_month is None:
            current_month = datetime.now().month

        upcoming = []
        for c in COMPETITIONS:
            months_away = (c.month - current_month) % 12
            upcoming.append({
                "id": c.id,
                "name": c.name,
                "month": c.month,
                "difficulty": c.difficulty,
                "months_away": months_away,
            })

        upcoming.sort(key=lambda x: x["months_away"])
        return upcoming

    def get_by_difficulty(self, difficulty: str) -> List[Dict[str, Any]]:
        """按难度筛选"""
        return [
            {
                "id": c.id,
                "name": c.name,
                "month": c.month,
                "difficulty": c.difficulty,
                "description": c.description,
            }
            for c in COMPETITIONS
            if c.difficulty == difficulty
        ]


# 全局实例
competition_calendar = CompetitionCalendar()
