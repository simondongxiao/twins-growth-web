# V2.3 验证报告

验证日期：2026-09-14。

## 本次执行

- Python/跨语言自动化用例：115项通过。覆盖原有底账、日期、归档、增量升级保护，以及新增主体归属、原话边界、发育参考状态。
- Chromium界面检查：40项通过。包括父母选项、同段多主体、收水者不变成递水者、含混代词、整段与片段回填Markdown、家长核对历史、参考节点边界、320/360/390/430/768/1366宽度。
- 公开模板隐私检查：通过；web只含程序与公开参考，不含家庭seed。
- 对V2.2交付包临时副本实际执行升级：通过。升级前所有事件ID保留，既有web/config.js未覆盖，新Markdown生成。未操作用户的D盘。

## 必须区别的范围

浏览器对localhost真实导航被运行环境策略阻止，因此界面测试用set_content、明确的存储替身和到真实Python HTTP服务的桥接完成。不是实体手机测试，也不是浏览器原生缓存持久化的实测。

没有连接实际GitHub/Supabase，没有在用户Windows电脑或父母实体手机部署。真实云端行级授权、双设备离线重连、公开站点更新和私有GitHub备份需Codex部署后复验。本次新增的40项界面检查没有重做真实云端验收。

主体分配为本地规则，不是大模型；测试覆盖明确的常见句型，不表示所有自然语言都能正确解析。歧义保留待确认。

参考模块是公开CDC精选观察点+家长记录，未经作为临床筛查工具验证，不输出诊断、发育商、超前月数或姐妹能力排名。

## 界面检查明细

- Only two parent writer buttons
- No caregiver writer setting
- Three child views preserved
- Four mobile actions including reference
- Single paragraph split into A / B / shared
- Correct subject routing
- Recipient A not copied as the actor
- Yesterday inherited across same report
- One immutable original paragraph saved
- Three exact fragments authored by mother
- Original paragraph written to Markdown
- Recipient behavior not copied to A Markdown
- A history has contextual references for A/shared only
- Current 18-month selected references visible
- 75 percent node boundary visible
- Missing logs remain unknown
- 24-month preview has selected nine items
- Pre-node not-yet is not delayed
- Milestone check has Markdown audit
- Lost skill prompts consultation at any age
- Check history preserved, not overwritten
- Ambiguous she is not assigned by guess
- Unresolved history offers one-tap subject correction
- Correction retains withdrawn old entry
- Correction creates new explicit B entry
- Different dates resolved per fragment
- No horizontal page overflow at 320px
- Reference has no page overflow at 320px
- No horizontal page overflow at 360px
- Reference has no page overflow at 360px
- No horizontal page overflow at 390px
- Reference has no page overflow at 390px
- No horizontal page overflow at 430px
- Reference has no page overflow at 430px
- No horizontal page overflow at 768px
- Reference has no page overflow at 768px
- No horizontal page overflow at 1366px
- Reference has no page overflow at 1366px
- Existing one-click archive action preserved
- No browser JavaScript errors
