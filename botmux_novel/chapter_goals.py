from __future__ import annotations


def chapter_goal_for(chapter_number: int) -> str:
    goals = {
        1: "用旧书楼残页引出主角秘密能力并埋下巡夜钟伏笔。",
        2: "让林烬用半张残页验证巡夜钟异常，并把妹妹影子证词转成下一章追查目标。",
        3: "让林烬追查巡夜钟提前响起的原因，发现夜巡记录被人为改写。",
        4: "让玄衣巡使从压迫者变成可疑盟友，暴露真正执棋者的外层线索。",
        5: "让林烬公开利用影子证词反击一次清查，并留下第一卷中段反转钩子。",
    }
    return goals.get(
        chapter_number,
        f"推进第 {chapter_number} 章主线，回收前文章节事实并新增可追踪伏笔。",
    )
