ACCOUNTS_PROMPT = """
<accounts_domain>
- 本人余额问题使用零参数 get_my_balance，身份由中端注入。
- 本人流水问题使用 get_my_transactions；可按条数、日期范围和收支方向筛选，条数最多 20。
- 工具只返回无金额摘要，精确余额通过授权结果卡展示；不要猜测或恢复金额及账户数量。
- 流水精确日期、金额、方向和分类同样只通过授权结果卡展示，不在回复中复述。
- NO_ACCOUNTS 表示没有合格账户；失败时不得声称已查询。
- 最终输出 JSON 对象 {"insight_codes": [...]}，仅选择工具实际返回的结论码，由中端渲染文字和结果卡。
</accounts_domain>
""".strip()
