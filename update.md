修改的文件

app.py
新增 Comment 数据模型（id, content, created_at, user_id, note_id）
User 添加 comments relationship
Note 添加 comments relationship（按时间倒序）
新增 4 个路由：
GET /plaza — 广场主页，展示所有公开笔记，支持搜索
GET /plaza/<id> — 广场内查看笔记详情
POST /plaza/<id>/comment — 发表评论
POST /comments/<id>/delete — 删除自己的评论

base.html — 导航栏新增「笔记广场」按钮

index.html — 右侧栏新增笔记广场快捷入口卡片view_note.html — 公开笔记旁新增「在广场中查看」按钮


新建的文件
plaza.html — 广场主页模板，展示所有公开笔记卡片（作者、标签、摘要、评论数），支持搜索plaza_note.html — 广场笔记详情页，Markdown 渲染 + 评论区 + 发表评论表单 + 删除自己的评论
启动方式：python app.py，首次启动会自动创建 comment 表