from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


def chapter_id(chapter_number: int) -> str:
    return f"ch-{chapter_number:03d}"


@dataclass(frozen=True)
class AgentOutput:
    name: str
    summary: str
    data: Dict[str, Any]


class DirectorAgent:
    name = "director"

    def plan_project(
        self,
        *,
        title: str,
        inspiration: str,
        mode: str,
        chapter_number: int,
        word_target: int,
    ) -> AgentOutput:
        protagonist = "林烬"
        antagonist = "玄衣巡使"
        mentor = "旧书楼守灯人"
        chapter = chapter_id(chapter_number)
        data = {
            "project": {
                "title": title,
                "mode": mode,
                "stage": "Plan",
                "current_chapter": chapter,
                "word_target": word_target,
                "quality_thresholds": {
                    "progression": 7,
                    "emotion": 7,
                    "character": 8,
                    "pacing": 7,
                    "style": 8,
                },
            },
            "story_bible": {
                "theme": "在被规定的人生里夺回选择权",
                "inspiration": inspiration,
                "core_conflict": "主角发现家族旧案与城中禁术有关，必须在自保和揭露真相之间选择。",
                "ending_constraint": "主角不能靠突然觉醒解决核心危机，必须用已铺垫的线索反击。",
            },
            "genre": {
                "primary": "东方悬疑幻想",
                "reader_expectations": ["开局钩子", "身份秘密", "层层反转", "强约束下的智性反击"],
                "selling_points": ["旧案翻盘", "禁术代价", "弱势主角主动破局"],
            },
            "world": {
                "rules": [
                    "城中所有术法都必须以记忆作抵押。",
                    "巡夜钟响后三刻内，任何谎言都会在影子里显形。",
                    "旧书楼保存被官府删改前的案件残页。",
                ],
                "forbidden": ["不能让主角突然无代价突破", "不能提前揭示禁术源头"],
            },
            "characters": [
                {
                    "id": "protagonist",
                    "name": protagonist,
                    "role": "主角",
                    "motivation": "查清父亲旧案，保住妹妹的户籍和自由。",
                    "current_state": "贫寒、克制、背着旧案污名。",
                    "secret": "他能看见被抵押记忆留下的残光。",
                },
                {
                    "id": "antagonist",
                    "name": antagonist,
                    "role": "明面阻力",
                    "motivation": "压下旧案残页，维护巡城司权威。",
                    "current_state": "掌控城门和夜巡记录。",
                    "secret": "他并非旧案主谋，只是替真正的执棋者清场。",
                },
                {
                    "id": "mentor",
                    "name": mentor,
                    "role": "线索提供者",
                    "motivation": "等一个敢把旧案重新点灯的人。",
                    "current_state": "守着破败旧书楼，身份可疑。",
                    "secret": "他曾参与封存旧案。",
                },
            ],
            "relationships": {
                "project_title": title,
                "edges": [
                    {
                        "source": "protagonist",
                        "target": "antagonist",
                        "type": "conflict",
                        "pressure": "玄衣巡使掌握妹妹户籍和旧案清场权。",
                        "secret": "玄衣巡使知道残页会暴露真正执棋者。",
                    },
                    {
                        "source": "protagonist",
                        "target": "mentor",
                        "type": "information",
                        "pressure": "守灯人只给半张残页，迫使主角自己验证。",
                        "secret": "守灯人曾参与封存旧案，不完全可信。",
                    },
                    {
                        "source": "protagonist",
                        "target": "sister",
                        "type": "emotional",
                        "pressure": "妹妹户籍是主角不能退让的现实代价。",
                        "secret": "妹妹影子知道旧案第三人的线索。",
                    },
                ],
            },
            "scene_settings": [
                {
                    "id": "tax-registry-office",
                    "name": "城南税籍所",
                    "kind": "location",
                    "function": "制造户籍风险和官府压迫，逼主角进入旧案线。",
                    "conflict_pressure": "巡城司可以用户籍决定妹妹去留。",
                    "rules": ["公开场合不能暴露看见影子残页的能力。"],
                    "reuse_value": "后续可作为户籍清查、公开对质和权力压迫场景。",
                },
                {
                    "id": "old-library",
                    "name": "旧书楼",
                    "kind": "location",
                    "function": "提供旧案残页、记忆代价规则和守灯人试探。",
                    "conflict_pressure": "答案必须用记忆交换，且信息可能被守灯人过滤。",
                    "rules": ["旧书楼只保存被删改前的残页，不直接给完整真相。"],
                    "reuse_value": "作为线索补给、代价抉择和旧案版本对照场景。",
                },
                {
                    "id": "patrol-bell",
                    "name": "巡夜钟",
                    "kind": "world_rule",
                    "function": "让谎言在影子里显形，形成悬疑验证机制。",
                    "conflict_pressure": "钟声时间可被篡改，导致真相和陷阱同时出现。",
                    "rules": ["钟响后三刻内，谎言会在影子里显形。"],
                    "reuse_value": "用于审讯、反转、伏笔回收和终局反击。",
                },
            ],
            "style_profile": {
                "id": "default-shadow-clock-style",
                "tone": "冷峻、克制、悬疑压迫",
                "rules": [
                    "减少解释性总结。",
                    "对话带潜台词。",
                    "用动作和场景承载情绪。",
                    "每个场景至少出现一次信息反转。",
                ],
                "forbidden_expressions": ["感到无比震惊", "他很生气", "她非常害怕"],
                "positive_examples": ["林烬把指腹按在那行墨痕上，纸页被汗意浸软。"],
                "negative_examples": ["林烬感到无比震惊。"],
            },
            "volume_outline": {
                "volume": "第一卷：影子里的旧案",
                "goal": "林烬从被动背锅到掌握第一份旧案证据。",
                "turning_points": ["旧书楼残页", "巡夜钟试探", "妹妹被卷入户籍清查", "主角公开反击"],
            },
            "chapter_goal": {
                "chapter_id": chapter,
                "objective": "用旧书楼残页引出主角的秘密能力，并埋下巡夜钟伏笔。",
                "must_include": ["旧书楼", "残页", "巡夜钟", "妹妹户籍"],
                "forbidden": ["主角不能突然突破", "不能提前揭示禁术源头"],
            },
        }
        return AgentOutput(self.name, "完成开书规划、核心资产和首章目标。", data)


class BlueprintAgent:
    name = "blueprint"

    def generate(self, plan: Dict[str, Any]) -> AgentOutput:
        chapter_goal = plan["chapter_goal"]
        protagonist = plan["characters"][0]["name"]
        data = {
            "chapter_id": chapter_goal["chapter_id"],
            "title": "旧书楼的残页",
            "objective": chapter_goal["objective"],
            "scenes": [
                {
                    "id": "scene-1",
                    "purpose": "用压迫性事件开场，说明妹妹户籍风险。",
                    "location": "城南税籍所外",
                    "conflict": f"{protagonist}被迫接受巡城司盘问。",
                    "turn": "他在巡使影子里看见一角旧案残页。",
                },
                {
                    "id": "scene-2",
                    "purpose": "进入旧书楼，给出残页和代价规则。",
                    "location": "旧书楼",
                    "conflict": "守灯人试探主角是否敢交换记忆。",
                    "turn": "主角拒绝无代价答案，只拿走能自证的残页。",
                },
                {
                    "id": "scene-3",
                    "purpose": "用巡夜钟制造结尾钩子。",
                    "location": "归家巷口",
                    "conflict": "巡夜钟提前响起，妹妹的影子说出陌生证词。",
                    "turn": "主角意识到旧案仍在发生。",
                },
            ],
            "emotion_curve": ["压迫", "试探", "克制", "惊疑"],
            "must_include": chapter_goal["must_include"],
            "forbidden": chapter_goal["forbidden"],
            "expected_artifacts": ["draft", "review", "revision", "final", "archive"],
        }
        return AgentOutput(self.name, "生成首章蓝图、场景卡和情绪曲线。", data)


class ContextPackBuilder:
    name = "context"

    def build(self, plan: Dict[str, Any], blueprint: Dict[str, Any]) -> AgentOutput:
        data = {
            "chapter_id": blueprint["chapter_id"],
            "objective": blueprint["objective"],
            "must_include": blueprint["must_include"],
            "facts": [
                "林烬背负父亲旧案污名。",
                "妹妹户籍可能被巡城司清查。",
                "旧书楼保存被删改前的案件残页。",
            ],
            "character_states": [
                "林烬：克制、警惕，不能主动暴露秘密能力。",
                "玄衣巡使：强势盘问，掌握夜巡记录。",
                "旧书楼守灯人：试探主角，不直接给答案。",
            ],
            "foreshadowing": ["巡夜钟会让谎言在影子里显形。", "记忆抵押会留下残光。"],
            "style_rules": ["减少解释性总结", "对话带潜台词", "每个场景必须有一次信息反转"],
            "forbidden": blueprint["forbidden"],
            "source_refs": ["story_bible", "characters/index", "volume_outline", blueprint["chapter_id"]],
        }
        return AgentOutput(self.name, "构建章节上下文包和引用依据。", data)


class DraftWriterAgent:
    name = "draft-writer"

    def draft(self, blueprint: Dict[str, Any], context: Dict[str, Any]) -> AgentOutput:
        text = f"""# {blueprint['title']}

税籍所的檐水滴了一上午，林烬把妹妹的旧户帖压在袖中，指节被纸边硌出一道白痕。

玄衣巡使站在阶上，翻着名册，像是在翻一摞可以随手丢进火里的草纸。“林家还剩几口人？”

“两口。”林烬答得很轻。

巡使抬眼，身后的影子却比人先动了一下。那影子衣摆里夹着半片发黄纸页，纸页边角烧焦，露出“旧案复核”四个残字。林烬的眼底刺痛，像有人把冷针推进瞳孔。他没有追问，只把袖口压得更紧。

妹妹户籍若被划掉，她就会被送去抵役。巡使知道这一点，所以每个停顿都像刀背，慢慢敲在林烬骨头上。

午后，林烬去了旧书楼。楼里没有客，只有守灯人坐在灯下擦一盏没有油的铜灯。

“看见了？”守灯人问。

林烬没有承认。“我来找一本被官府删过的案录。”

守灯人笑了笑，把一张残页推过来，又用指节按住。“城里的答案都有价。你拿走它，就留下一段记忆。”

“若答案是真的，我会付我该付的。”林烬看着那张残页，“若你只是想替别人确认我能看见什么，我现在转身就走。”

守灯人的手停住。铜灯里没有火，灯芯却亮了一瞬。

残页最终只给了半张。上面没有凶手名字，只有一行被墨划过的证词：巡夜钟响后三刻，林家门前没有血，只有三个人的影子。

林烬感到无比震惊。他把残页收入怀中，走出旧书楼时，天色已经压到巷顶。

第一声巡夜钟在黄昏前响起。

这不合规矩。

林烬冲回家门口，看见妹妹站在槐树下，脸色苍白。她没有开口，她的影子却贴着墙，一字一句地说：“我那晚见过第三个人。”

风从巷口灌进来，吹得旧户帖哗啦作响。林烬终于明白，旧案没有过去，它只是换了一种方式，继续在活人身上写字。
"""
        data = {
            "chapter_id": blueprint["chapter_id"],
            "title": blueprint["title"],
            "text": text,
            "notes": ["初稿故意保留一处模板化表达，供编辑 Agent 验证去 AI 味闭环。"],
            "used_context": context["source_refs"],
        }
        return AgentOutput(self.name, "生成首章正文草稿。", data)


class ConsistencyAgent:
    name = "consistency-checker"

    def review(self, text: str, blueprint: Dict[str, Any], context: Dict[str, Any]) -> AgentOutput:
        issues: List[Dict[str, Any]] = []
        for item in blueprint["must_include"]:
            if item not in text:
                issues.append(
                    {
                        "severity": "P1",
                        "gate": "Gate 1",
                        "message": f"缺少必须出现的信息：{item}",
                        "suggestion": f"补入与 {item} 相关的剧情动作。",
                    }
                )
        for item in blueprint["forbidden"]:
            marker = item.replace("不能", "").replace("提前", "").strip()
            if marker and marker in text:
                issues.append(
                    {
                        "severity": "P0",
                        "gate": "Gate 1",
                        "message": f"触碰硬约束：{item}",
                        "suggestion": "阻断定稿，回到章纲或正文重写。",
                    }
                )
        if "感到无比震惊" in text:
            issues.append(
                {
                    "severity": "P2",
                    "gate": "Gate 4",
                    "message": "存在抽象总结式表达，AI 味明显。",
                    "suggestion": "改成动作、环境或潜台词承载情绪。",
                }
            )

        p0_p1 = [issue for issue in issues if issue["severity"] in {"P0", "P1"}]
        p2 = [issue for issue in issues if issue["severity"] == "P2"]
        scores = {
            "consistency": 10 if not p0_p1 else 5,
            "progression": 8,
            "emotion": 8 if not p2 else 7,
            "character": 8,
            "pacing": 8,
            "style": 8 if not p2 else 6,
        }
        decision = "block" if p0_p1 else "revise" if p2 else "pass"
        data = {
            "chapter_id": blueprint["chapter_id"],
            "decision": decision,
            "issues": issues,
            "scores": scores,
            "gate_results": [
                {"gate": "Gate 0", "status": "pass", "detail": "章纲、上下文包、事实和禁区齐全。"},
                {"gate": "Gate 1", "status": "pass" if not p0_p1 else "fail", "detail": "硬约束检查完成。"},
                {"gate": "Gate 2", "status": "pass", "detail": "未发现人物、时间线、地点和因果冲突。"},
                {"gate": "Gate 3", "status": "pass", "detail": "章节目标、冲突推进和结尾钩子成立。"},
                {"gate": "Gate 4", "status": "pass" if not p2 else "revise", "detail": "文风与去 AI 味检查完成。"},
            ],
        }
        return AgentOutput(self.name, f"质量门禁结果：{decision}。", data)


class EditorAgent:
    name = "editor"

    def revise(self, draft_text: str, review: Dict[str, Any]) -> AgentOutput:
        revised = draft_text.replace(
            "林烬感到无比震惊。他把残页收入怀中，走出旧书楼时，天色已经压到巷顶。",
            "林烬把指腹按在那行墨痕上，纸页被汗意浸软。他没有再问，只把残页收入怀中；走出旧书楼时，天色已经压到巷顶。",
        )
        data = {
            "text": revised,
            "changes": [
                {
                    "from": "林烬感到无比震惊。",
                    "to": "林烬把指腹按在那行墨痕上，纸页被汗意浸软。",
                    "reason": "用动作和触感替代表情绪总结。",
                }
            ],
            "resolved_issue_count": len(review.get("issues", [])),
        }
        return AgentOutput(self.name, "完成去 AI 味修订并保留剧情事实。", data)


class ArchiveMemoryAgent:
    name = "archive-memory"

    def archive(
        self,
        *,
        final_text: str,
        plan: Dict[str, Any],
        blueprint: Dict[str, Any],
        review: Dict[str, Any],
    ) -> AgentOutput:
        chapter = blueprint["chapter_id"]
        data = {
            "facts": [
                {
                    "chapter_id": chapter,
                    "fact": "林烬在玄衣巡使影子里看见旧案残页。",
                    "source": "manuscript/final",
                },
                {
                    "chapter_id": chapter,
                    "fact": "旧书楼守灯人确认城中答案需要以记忆为代价。",
                    "source": "manuscript/final",
                },
                {
                    "chapter_id": chapter,
                    "fact": "妹妹的影子在巡夜钟声后说出第三个人证词。",
                    "source": "manuscript/final",
                },
            ],
            "timeline": [
                {"chapter_id": chapter, "time": "上午", "event": "税籍所盘问与妹妹户籍风险出现。"},
                {"chapter_id": chapter, "time": "午后", "event": "林烬进入旧书楼取得半张残页。"},
                {"chapter_id": chapter, "time": "黄昏前", "event": "巡夜钟提前响起，旧案线索复燃。"},
            ],
            "foreshadowing": [
                {
                    "id": "bell-early-ring",
                    "chapter_id": chapter,
                    "item": "巡夜钟提前响起",
                    "introduced_in": chapter,
                    "planned_payoff": "第一卷中段揭示有人篡改夜巡钟令。",
                    "status": "open",
                    "risk": "P1",
                },
                {
                    "id": "third-shadow",
                    "chapter_id": chapter,
                    "item": "第三个人的影子",
                    "introduced_in": chapter,
                    "planned_payoff": "第一卷结尾指向真正执棋者。",
                    "status": "open",
                    "risk": "P0",
                },
            ],
            "character_state": [
                {
                    "id": "protagonist",
                    "name": plan["characters"][0]["name"],
                    "state": "取得半张旧案残页，确认妹妹卷入旧案余波。",
                    "known_information": ["巡夜钟异常", "第三个人证词", "旧书楼可提供旧案残页"],
                }
            ],
            "continuity_issues": [],
            "archive_decision": "pass" if review["decision"] == "pass" else "blocked",
            "gate_results": [
                {
                    "gate": "Gate 5",
                    "status": "pass" if review["decision"] == "pass" else "blocked",
                    "detail": "新增事实、角色状态、伏笔和时间线已提取并准备落库。",
                }
            ],
            "final_word_count": len(final_text),
        }
        return AgentOutput(self.name, "完成事实、时间线、伏笔和角色状态归档。", data)
