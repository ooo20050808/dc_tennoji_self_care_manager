import random
from datetime import datetime, timedelta, time
from django.core.management.base import BaseCommand
from django.utils import timezone
from selfCare.models import User, HomeScreen, InputScreen, SaturdayOpening


class Command(BaseCommand):
    help = '1月から10月（または11月以降）までの勤怠・生活テストデータを自動生成します。'

    def handle(self, *args, **options):
        current_year = timezone.now().year

        # 1. 対象期間の設定（例: 1月1日から10月31日まで。11月以降の場合は必要に応じて終了日を調整してください）
        start_date = datetime(current_year, 1, 1).date()

        # 現在の月や「11月になったら11月も」というご要望に合わせて、今日が属する月（または10月・11月）まで動的に設定
        today = timezone.now().date()
        target_end_month = max(10, today.month) if today.year == current_year else 10
        if target_end_month > 12:
            target_end_month = 12

        # 各月の最終日を計算するための簡易処理（ここでは10月または11月末まで、安全に10月31日または11月30日まで）
        # ※ 1月〜10月を確実に網羅したい場合は以下のように直接10月31日などに設定可能です
        end_date = datetime(current_year, 10, 31).date()
        # 11月以降のデータも入れる場合は、end_dateを適宜拡張してください（例: datetime(current_year, 11, 30).date()）

        users = User.objects.filter(user_role=1)
        if not users.exists():
            self.stdout.write(self.style.ERROR('対象となる利用者（user_role=1）が存在しません。'))
            return

        self.stdout.write(self.style.NOTICE(f'{start_date} から {end_date} までのテストデータ生成を開始します...'))

        # 2. 期間内の土曜日をランダムに「土曜開所日 (SaturdayOpening)」として登録する
        current_date = start_date
        saturday_created_count = 0
        while current_date <= end_date:
            if current_date.weekday() == 5:  # 土曜日
                # 40%の確率で土曜開所日としてランダム登録
                if random.random() < 0.4:
                    SaturdayOpening.objects.get_or_create(
                        open_date=current_date,
                        defaults={'registered_by': users.first()}
                    )
                    saturday_created_count += 1
            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f'土曜開所日を {saturday_created_count} 日分ランダム登録しました。'))

        # 3. 動的生成用のバリエーション候補（毎回ランダムに選択）
        morning_works = [
            '基礎スキル学習（Python/Django）',
            'データ入力・ファイル整理',
            'タイピング練習・PC基本操作',
            '朝礼・体調確認・軽作業',
            'Webアプリケーション機能実装'
        ]
        afternoon_works = [
            'グループワーク・掲示板機能開発',
            'データベース設計・SQL演習',
            '振り返りシート作成・コードレビュー',
            'API連携テスト・エラーハンドリング',
            '自由学習・ポートフォリオ作成'
        ]
        user_comments = [
            '体調は概ね安定しており、集中して作業に取り組めました。',
            '少し疲れを感じましたが、最後までやり遂げました。',
            '分からない箇所をスタッフの方に質問し、無事に解決できました。',
            '自分のペースで着実にスキルアップが進んでいる実感があります。',
            '特段問題ありません。明日もこの調子で頑張ります。'
        ]
        staff_comments = [
            'お疲れ様でした。熱心に取り組んでおり素晴らしいです。',
            '体調管理に気をつけながらよく頑張りました。',
            '質問を積極的に行っていて良い姿勢です。',
            '着実に成果が出ています。この調子で進めましょう。',
            '確認しました。体調を崩さないよう無理せずいきましょう。'
        ]

        # 4. 日ごとの勤怠・生活データの生成ループ
        current_date = start_date
        total_created = 0

        while current_date <= end_date:
            weekday = current_date.weekday()

            # 日曜日はスキップ (6: 日曜)
            if weekday == 6:
                current_date += timedelta(days=1)
                continue

            # 土曜日の場合、SaturdayOpeningに登録されている開所日かチェック
            if weekday == 5:
                is_open_saturday = SaturdayOpening.objects.filter(open_date=current_date).exists()
                if not is_open_saturday:
                    current_date += timedelta(days=1)
                    continue

            for user in users:
                home_screen, _ = HomeScreen.objects.get_or_create(
                    user=user,
                    date=current_date
                )

                # 在宅チェックをランダムに設定（35%の確率で在宅＝True）
                at_home = random.random() < 0.35

                # 入室・退出時刻: 10:00〜16:00 の15分刻み
                time_slots = []
                for h in range(10, 16):
                    for m in range(0, 60, 15):
                        time_slots.append(time(h, m))
                time_slots.append(time(16, 0))

                entry_t = random.choice(time_slots[:len(time_slots) // 2])
                valid_leaving_slots = [t for t in time_slots if t > entry_t]
                if not valid_leaving_slots:
                    valid_leaving_slots = [time(16, 0)]
                leaving_t = random.choice(valid_leaving_slots)

                # 睡眠時間: 0〜24時間のランダム（0.5時間刻み）
                sleep_hours = round(random.choice([i * 0.5 for i in range(0, 49)]), 1)

                # 服薬チェック: 「全てTrue」「いずれかFalse」「全てFalse」のいずれか
                med_pattern = random.choice(['all_true', 'some_false', 'all_false'])
                if med_pattern == 'all_true':
                    med_m, med_n, med_nig = True, True, True
                elif med_pattern == 'all_false':
                    med_m, med_n, med_nig = False, False, False
                else:
                    med_m = random.choice([True, False])
                    med_n = random.choice([True, False])
                    med_nig = random.choice([True, False])

                # 体調
                condition = random.choices(['〇', '△', '✕'], weights=[75, 20, 5])[0]

                # 入退室時刻の割り振り（在宅か通所かでビューの仕様に合わせてフィールドを切り分け）
                defaults_data = {
                    'at_home': at_home,
                    'sleep_time_hours': sleep_hours,
                    'condition': condition,
                    'medication_morning': med_m,
                    'medication_noon': med_n,
                    'medication_night': med_nig,
                    'morning_work_content': random.choice(morning_works),
                    'afternoon_work_content': random.choice(afternoon_works),
                    'user_comment': random.choice(user_comments),
                    'staff_comment': random.choice(staff_comments),
                }

                if at_home:
                    defaults_data['staff_entry_time'] = entry_t
                    defaults_data['staff_leaving_time'] = leaving_t
                    defaults_data['entry_time'] = None
                    defaults_data['leaving_time'] = None
                else:
                    defaults_data['entry_time'] = entry_t
                    defaults_data['leaving_time'] = leaving_t
                    defaults_data['staff_entry_time'] = None
                    defaults_data['staff_leaving_time'] = None

                input_screen, created = InputScreen.objects.get_or_create(
                    user=user,
                    date=home_screen,
                    defaults=defaults_data
                )
                if created:
                    total_created += 1

            current_date += timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(f'処理が完了しました。合計 {total_created} 件のテストデータを生成しました。'))