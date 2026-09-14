# V2.2 测试与未完成项

执行日期：2026-09-14。

## 已运行

- 核心、日期、协作、GitHub保护测试：78个pytest用例通过。命令：`python -m pytest tests/test_core.py tests/test_time_age.py tests/test_handoff.py -q`。
- Chromium界面检查：43项通过，无JavaScript错误。
- 屏幕宽度：320、360、390、430、768、1366像素，记录/历史/同步视图均无横向溢出。390×844首屏可看到保存按钮。
- 一个独立升级场景：既有观察保留、既有web/config.js保留、private同步配置保留、新一键命令可用。
- 公开模板保护脚本通过：不含private seed、家庭生日、家庭原话或真实密钥。

## 浏览器测试的实际条件

当前环境禁止浏览器导航到localhost（ERR_BLOCKED_BY_ADMINISTRATOR）。界面检查使用Chromium的set_content，在Python桥接下调用真实本机HTTP服务；浏览器存储使用隔离的测试替身。

云端和GitHub测试使用模拟API，验证排队、失败、重复ID去重、回执与拒绝公开仓库等程序逻辑，不代表真实Supabase行级权限和真实GitHub账户已验证。

全部测试观察只存在临时目录或模拟云端，未写入交付的家庭growth.json。交付档案仍为原始基线、资料确认及候选计划。

## 尚未验证 / 尚未实施

未实际部署GitHub Pages；未创建或登录用户的Supabase；未验证真实RLS；未向真实私有GitHub提交备份；未在用户Windows电脑和父母两部手机上测试原生存储、系统分享和联网同步。

真实部署后，必须完成妈妈手机保存→爸爸电脑一键归档→妈妈看到回执的端到端验收。不把本报告当上线证明。

## 界面检查明细

- Top navigation retains big/small/comparison
- Bottom navigation has capture/history/sync
- Save button visible in initial 390x844 viewport
- Phone input font is 16px
- Primary save tap target at least 44px
- Relative date preview uses frozen report time
- Browser save writes actual local Markdown through HTTP
- Mother identity retained on observation
- History view displays saved observation
- Mother history filter works
- One-click local mode never claims missing cloud was synced
- One-click creates actual local archive receipt
- History shows per-record archive receipt
- Calendar in history can open the capture form without losing the chosen date
- No horizontal overflow at 320px / capture
- No horizontal overflow at 320px / history
- No horizontal overflow at 320px / sync
- No horizontal overflow at 360px / capture
- No horizontal overflow at 360px / history
- No horizontal overflow at 360px / sync
- No horizontal overflow at 390px / capture
- No horizontal overflow at 390px / history
- No horizontal overflow at 390px / sync
- No horizontal overflow at 430px / capture
- No horizontal overflow at 430px / history
- No horizontal overflow at 430px / sync
- No horizontal overflow at 768px / capture
- No horizontal overflow at 768px / history
- No horizontal overflow at 768px / sync
- No horizontal overflow at 1366px / capture
- No horizontal overflow at 1366px / history
- No horizontal overflow at 1366px / sync
- Comparison uses eight mobile cards instead of a wide table
- Comparison has no horizontal overflow
- Drafts survive reinitialization from device storage
- Failed upload keeps queued event in device ledger
- No fake cloud success when server rejects upload
- Selected child is retained in queued cloud observation
- Mother sees explicit pending-upload status
- Retry uploads exactly once by immutable ID
- Cloud confirmation changes only after verified readback
- Mother receives father archive receipt through shared history
- No browser JavaScript errors
