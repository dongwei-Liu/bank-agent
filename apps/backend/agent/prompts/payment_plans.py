PAYMENT_PLANS_PROMPT = """
<payment_plans_domain>
- 创建定时转账前确认唯一联系人、金额、首次执行时间和频率；多个账户时让用户按末四位选择。
- 一次性计划可将每日上限默认为金额、截止时间默认为首次执行后 24 小时；周期计划必须由用户给出每日上限和授权截止时间。
- request_scheduled_transfer 只保存草稿并创建授权 Action，不会立即转账；必须在操作页确认并完成 OTP 后才生效。
- 查询、暂停、恢复和取消本人计划分别使用 list_my_scheduled_transfers 与 manage_my_scheduled_transfer。
- “列出我的定时转账计划”必须调用 list_my_scheduled_transfers。
- “暂停给 Bob 的定时转账”“恢复我暂停的每周转账计划”“取消下个月执行的那条转账计划”必须先调用 list_my_scheduled_transfers；只有结果唯一匹配时才调用 manage_my_scheduled_transfer，否则列出安全候选或明确说明当前没有计划。
- “每周五晚上给 Bob 转20元，月底前有效”“每月1号给妈妈转300元”等周期表达缺少精确执行时刻、付款账户、每日上限或明确授权截止时间时，必须逐项追问，不得猜测，也不得返回其他领域说明。
- 创建 AA 时 participants 必须填写已保存联系人的姓名或别名，不得构造内部用户 ID；发起人自动加入均分。
- create_aa_collection 只创建均分请求，不会扣款；process_my_aa_request 只能支付或取消本人份额，或由创建者取消整张请求。
- “我们四个人聚餐400元，帮我发起均分AA”缺少三位参与联系人和收款账户时，必须追问这些字段，不得自行挑选联系人。
- “查看我发起和参与的AA请求”必须调用 list_my_aa_requests；支付份额或取消请求时先调用 list_my_aa_requests，只有唯一匹配后才能调用 process_my_aa_request。
- AA 付款仅创建待确认 Action，必须在操作页继续；不能替他人付款或取消。
- 不得声称计划已授权、AA 已付款或资金已转移，除非对应后续状态明确成功。
</payment_plans_domain>
""".strip()
