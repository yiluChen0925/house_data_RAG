# -*- coding: utf-8 -*-
"""验证报表链路能生成内容，且不会真的推送。

做法：把"今天"冻结成数据里最新的日期（否则日期窗口命中不到数据），
并把 push_report 换成空操作——不会发钉钉、不会发邮件。会真实调用 DeepSeek。

    python 5_tests/smoke/check_reports.py
"""

import datetime
import sys

sys.path.insert(0, __file__.rsplit("5_tests", 1)[0] + "5_tests")
import paths  # noqa: E402

paths.offline()
paths.add_paths()

import pandas as pd  # noqa: E402

SENT = []


def main():
    import push_report as pr

    def fake_push(content, report_type):
        SENT.append(report_type)
        print("  [拦截] push_report(%s, %d 字符) —— 未发送" % (report_type, len(content)))
        return True

    pr.push_report = fake_push

    df = pd.read_csv(paths.CLEANED_CSV, encoding='utf-8-sig')
    dates = pd.to_datetime(df['爬取时间'].astype(str).str[:10], errors='coerce')
    latest = dates.max()
    print('数据最新日期 %s，当天 %d 条' % (latest.strftime('%Y-%m-%d'), int((dates == latest).sum())))

    class FrozenNow(datetime.datetime):
        _fixed = datetime.datetime(latest.year, latest.month, latest.day, 12, 0, 0)

        @classmethod
        def now(cls, tz=None):
            return cls._fixed

    datetime.datetime = FrozenNow

    import daily_report
    import weekly_report

    d = daily_report.load_data()
    stats = daily_report.calc_today_stats(d)
    if stats:
        content = daily_report.generate_report(stats, daily_report.calc_historical_compare(d))
        print('\n日报 %d 字符，前 200 字：\n%s' % (len(content), content[:200]))
        print('  明细: 新增 %d, 最热区域 %s' % (stats['新增房源数'], stats['最热区域']))
    else:
        print('\n!! 日统计为空')

    w = weekly_report.load_data()
    wstats = weekly_report.calc_weekly_stats(w)
    if wstats:
        content = weekly_report.generate_weekly_report(wstats)
        print('\n周报 %d 字符，前 200 字：\n%s' % (len(content), content[:200]))
    else:
        print('\n!! 周统计为空')

    print('\n推送调用记录（应为空）: %s' % (SENT if SENT else '无'))


if __name__ == "__main__":
    main()
