# 破格消费口 JSON Schema v1.0

用途：引擎 detect_patterns 加载破格表，命中 breaking 即降级标注。
标注方（hanako）按本格式落表，消费方（韩湘生）直接加载，无需二次转换。

## 顶层结构

```json
{
  "schema_version": "1.0",
  "generated": "2026-08-14",
  "source_tiers": {
    "original": "古籍原文有据，source 必须含具体篇目+版本（《全书》刻本差异要标）",
    "common": "通行归纳（教材/师承），source 必须含作者或教材名"
  },
  "authority_rank": {
    "1": "古籍原文（带篇目+版本），如《紫微斗数全书》各刻本、《骨髓赋》《太微赋》原典",
    "2": "宗师注疏（体系传承明确），如王亭之《中州派紫微斗数》、陆斌兆《紫微斗数评注》",
    "3": "通行教材/师承作者，如易水盟、神机阁等",
    "4": "网络资料/知乎系（无体系归属）"
  },
  "arbitration": "分歧时取 authority_rank 数值最小（最权威）的一套作为判定依据；次权威异议保留为注记，解读脚注带出，不删信息。同层同派内打架（如中州派师徒）先核条文语境，语境不同则并存不判冲突；语境确同才启用下一级仲裁",
  "patterns": {
    "<格局名>": {
      "base_level": "吉|中|忌|上吉",
      "grade_tiers": {
        "highest": "上格条件描述（如辰戌上格）",
        "mid": "次格条件描述（如丑未次格）",
        "low": "更次条件描述（如他宫更次）"
      },
      "breaking": [
        {
          "id": "ht-brk-001",
          "condition": "可判定条件描述（命中即触发破格）",
          "semantics": "reject|downgrade",
          "effect": "破格后的应事效果（供解读用）",
          "source_tier": "original|common",
          "source": "出处：教材名/作者 或 古籍篇目+版本",
          "status": "draft|verified",
          "disputed": false,
          "schools": ["持有此说法的派系/作者（disputed=true 时必填）"],
          "authority_rank": 2,
          "notes": "可选注记（如：铃贪不如火贪、章真言异说）"
        }
      ],
      "enhancer": [
        {
          "id": "spz-enh-001",
          "condition": "可判定条件描述（命中即加分，如杀破狼三方化禄/权、辅弼同会）",
          "effect": "加分效果描述",
          "source_tier": "original|common",
          "source": "出处",
          "status": "draft|verified"
        }
      ],
      "weakener": [
        {
          "id": "ht-wkn-001",
          "condition": "可判定条件描述（命中仅减分，不破格）",
          "effect": "减分效果描述",
          "source_tier": "original|common",
          "source": "出处",
          "status": "draft|verified",
          "disputed": false,
          "schools": [],
          "authority_rank": 2
        }
      ],
      "breaking_semantics": "hit_any_downgrade | hit_any_reject（pattern 级默认值，条目级 semantics 优先）"
    }
  }
}
```

## 字段语义

- `breaking_semantics`（pattern 级默认值）：
  - `hit_any_downgrade`：命中任一 breaking → level 降一档（上吉→吉→中→忌），仍报格局名但标注「破格」
  - `hit_any_reject`：命中任一 breaking → 格局不成立，从结果剔除（用于「擎羊与火星同度不成格」这类硬性排除）
- 条目级 `semantics`（breaking 数组内每条约）：reject / downgrade，优先于 pattern 级默认。火贪格这类混合语义（既有硬排除又有降级条）按条走，不归并
- `enhancer`：加分项，承接原 bonus（杀破狼三方化禄/权、辅弼同会）。命中提高解读强度，不改变 level 档位
- `weakener`：减分项。命中只减弱解读语气，不触发破格降级（紫贪同宫受帝曜制约、廉贪同宫发不能耐久、单见空劫制贪狼反习正这类）
- `notes`：注记位。条目的旁注信息（铃贪不如火贪、章真言异说等），不参与判定
- `disputed` + `schools` + `authority_rank`：派别分歧标记。true 时 schools 必填列出持此说的派系，authority_rank 必填（1=古籍原文带版本 / 2=宗师注疏 / 3=通行教材 / 4=网络）；消费端命中分歧条时按 rank 取最权威一套为判定依据，次权威异议保留为注记，解读脚注带出，不得选边当铁律（空劫制化贪狼即分歧样板）
- `grade_tiers`：成格分档（辰戌上格/丑未次格/他宫更次），供骨架表归档，不参与破格判定
- `condition`：必须是引擎可判定的描述（星曜、宫位、四化、庙陷的组合），自由散文进不了判定函数
- `status`：draft = 通行归纳待复核；verified = 已对原文/教材核实

## 样例（火贪格，取自 2026-08-14 网络核验）

```json
{
  "schema_version": "1.0",
  "generated": "2026-08-14",
  "source_tiers": {
    "original": "古籍原文有据，source 必须含具体篇目+版本（《全书》刻本差异要标）",
    "common": "通行归纳（教材/师承），source 必须含作者或教材名"
  },
  "patterns": {
    "火贪格": {
      "base_level": "吉",
      "breaking": [
        {
          "id": "ht-brk-001",
          "condition": "贪狼化忌且三方会昌曲",
          "effect": "暴发转暴败，摔下难翻身",
          "source_tier": "common",
          "source": "易水盟·三合火贪格详解",
          "status": "draft"
        },
        {
          "id": "ht-brk-002",
          "condition": "贪狼同宫见地空或地劫",
          "effect": "火星爆发力被吸蚀，横发机会大减",
          "source_tier": "common",
          "source": "易水盟·三合火贪格详解；王亭之《中州派紫微斗数》",
          "status": "draft"
        },
        {
          "id": "ht-brk-003",
          "condition": "擎羊或陀罗与贪狼同宫",
          "effect": "情感招祸，格局走偏",
          "source_tier": "common",
          "source": "易水盟·三合火贪格详解",
          "status": "draft"
        },
        {
          "id": "ht-brk-004",
          "condition": "擎羊或陀罗与火星同宫",
          "effect": "不符合火贪格（硬性排除）",
          "source_tier": "common",
          "source": "易水盟·三合火贪格详解",
          "status": "draft"
        }
      ],
      "breaking_semantics": "hit_any_reject"
    }
  }
}
```

## 说明

- 样例中 id 前缀 ht = 火贪格，按 `格局首字母拼音-brk-序号` 规则编号
- `hit_any_reject` vs `hit_any_downgrade` 由标注方按条文性质定：硬性排除（此格不成立）用 reject，强度减弱用 downgrade
- 判定函数实现由消费方负责，标注方只保证 condition 文本可判定
