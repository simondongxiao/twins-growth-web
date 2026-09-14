# V2.1 验证记录

执行日：2026-09-14。未连接家庭云端；以下为此工作环境的真实执行结果。

## 自动化核心检查

`python -m pytest -q tests/test_core.py tests/test_time_age.py`：60项通过。

覆盖V2原有增量合并、相同ID冲突、撤回、原始观察保留、备份、跨线程/进程写入；新增完整日历月＋余天、月末、闰年、自然周与滚动7日区分、跨年、UTC+8/UTC+9参考日期、模糊时间、多日期句子、日期区间、Python/JavaScript解析一致性、对话录入CLI、相同source_id去重、升级原项目不覆盖历史。

## 浏览器检查

`python tests/browser_dom.py`：原有12项界面检查通过。

`python tests/browser_calendar.py`：新增11项日历与时间检查通过。

实际使用Chromium，HTML以set_content载入；请求通过Python桥接到真实本机HTTP服务，浏览器存储用测试替身。验证从页面输入、日期预览、保存请求到临时目录Markdown回填，包含390px手机宽度无横向溢出。未把此环境的替身测试说成原生手机完整验收。

两次浏览器检查均没有JavaScript页面错误。所有演示/测试行为只写临时目录，不进入交付家庭底账。

## 发布检查

`python tools/check_public.py`通过。公开web文件不含生日及私有seed。完整包与私有独立HTML包含家庭资料，不可直接上传公开仓库。

## 未验收的项目

真实Windows批处理运行；父母实际手机浏览器；GitHub发布；真实Supabase身份验证与RLS；两部手机与电脑持续同步。代码和测试已交付，不代表这些部署已经完成。
