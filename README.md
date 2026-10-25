# 股指期货交割日订阅

每月第三个星期五为股指期货（IF/IC/IM/IH）交割日。
这个仓库每周自动重新生成 `calendar.ics`，苹果日历订阅后会定期拉取，
内容一改，你的日历自动跟着变，不用重新导入。

每个交割日有 4 个提醒：前 3 天、前 2 天、前 1 天每天早上 9 点各一次，
交割日当天早上 9 点一次。

## 部署（只需要做一次）

### 1. 新建仓库

GitHub 上新建一个仓库，名字随便（比如 `futures-calendar`），
**必须选 Public**（免费版 GitHub Pages 只支持公开仓库）。
日历里只有交割提醒，不含任何隐私内容，公开没有关系。

### 2. 把文件放进去

方法 A（会用 git）：把这个压缩包解压，把里面的文件全部拷进仓库，提交推送。

方法 B（不会 git，全程网页操作）：
- 仓库页面点 Add file → Upload files，上传 `generate_calendar.py`、`calendar.ics`、`README.md`、`.nojekyll`。
- 再点 Add file → Create new file，文件名一栏直接输入
  `.github/workflows/update.yml`，把 `update.yml` 的内容粘贴进去，提交。
  （文件名里带斜杠，GitHub 会自动建文件夹。）

### 3. 开启 Pages

仓库 Settings → Pages → Build and deployment：
- Source 选 Deploy from a branch
- Branch 选 main，文件夹选 /(root)，保存。

等一两分钟，打开下面的链接，能下载到 `calendar.ics` 就说明成功了：

```
https://你的GitHub用户名.github.io/仓库名/calendar.ics
```

### 4. iPhone 上订阅

设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历，
粘贴上面那个链接，点下一步 → 存储。

## 节假日顺延怎么更新

交割日变动没有交易所的实时推送接口，所以顺延是手动维护的，
但维护一次，所有订阅的人自动同步：

1. 每年国务院节假日安排公布后（一般年底公布次年），
   看一下有没有第三个周五撞上假期。
2. 有撞上的，就在 `generate_calendar.py` 的 `OVERRIDES` 里加一行，
   比如 `"2027-09-17": "2027-09-20"`（原定日期 → 实际日期）。
3. 提交后 Action 立刻重新生成并发布；每周一的定时任务也会兜底刷新。

临时变动（比如交易所发调整公告）也一样：改一行 OVERRIDES 提交，
订阅端下次刷新就同步。

## 已知待确认

- 2027 年的节假日安排尚未公布，当前 2027 年的日期全部按第三个周五排，
  安排公布后再补 OVERRIDES。
- 2027 年中秋在 9 月 15 日（周三），9 月 17 日那个交割日很可能撞上中秋假期、
  需要顺延，待官方安排公布后确认实际日期再写进 OVERRIDES。

## 文件说明

- `generate_calendar.py`：生成器，只用 Python 标准库，窗口为本月起往后 26 个月。
- `calendar.ics`：生成的日历文件，事件 UID 按日期固定，重新生成不会重复。
- `.github/workflows/update.yml`：每周一自动重新生成并提交的任务。
- `.nojekyll`：告诉 Pages 不要用 Jekyll 处理，直接原样发布。
