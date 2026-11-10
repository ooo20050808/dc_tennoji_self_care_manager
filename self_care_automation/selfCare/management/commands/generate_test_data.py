import random
from datetime import datetime, timedelta, time
from django.core.management.base import BaseCommand
from django.utils import timezone
from selfCare.models import User, HomeScreen, InputScreen, SaturdayOpening


class Command(BaseCommand):
    help = '1月1日から当月末日（または指定月）までの勤怠・生活テストデータを自動生成します。'

    def handle(self, *args, **options):
        now = timezone.now()
        current_year = now.year
        current_month = now.month

        # 1. 対象期間の設定（1月1日 〜 今月の末日まで自動設定）
        start_date = datetime(current_year, 1, 1).date()

        # 当月の最終日を自動計算
        if current_month == 12:
            end_date = datetime(current_year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(current_year, current_month + 1, 1).date() - timedelta(days=1)

        users = User.objects.filter(user_role=1)
        if not users.exists():
            self.stdout.write(self.style.ERROR('対象となる利用者（user_role=1）が存在しません。'))
            return

        # 土曜開所日の登録者（registered_by）とするスタッフユーザー（user_role=2）を取得
        staff_user = User.objects.filter(user_role=2).first()
        if not staff_user:
            self.stdout.write(
                self.style.WARNING('user_role=2のスタッフが存在しないため、その他のスタッフ/管理者を検索します。'))
            staff_user = User.objects.filter(user_role=3).first() or users.first()

        self.stdout.write(self.style.NOTICE(f'{start_date} から {end_date} までのテストデータ生成を開始します...'))

        # 2. 期間内の「土曜日（weekday()==5）」を一旦すべてクリアするか、既存をリセットして45%の確率で再登録
        SaturdayOpening.objects.filter(open_date__range=[start_date, end_date]).delete()

        current_date = start_date
        saturday_created_count = 0
        while current_date <= end_date:
            if current_date.weekday() == 5:
                if random.random() < 0.45:  # 登録率45%
                    SaturdayOpening.objects.create(
                        open_date=current_date,
                        registered_by=staff_user
                    )
                    saturday_created_count += 1
            current_date += timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(
                f'土曜開所日を45%の確率でランダム再登録しました（登録数: {saturday_created_count} 日分）。'))

        # 3. 動的生成用のバリエーション候補
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
            '体調は概ね安定しており、集中して作業に取り組みました。',
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

        # 体調詳細モーダルのコメント候補
        detail_good_choices = ['ぐっすり眠れて朝から爽快です。', '体調万全で、学習に集中できました。',
                               '特に問題なく、順調に過ごせました。']
        detail_caution_choices = ['少し睡眠不足ですが、午後から持ち直しました。',
                                  '肩こりがありますが、体調不良というほどではありません。',
                                  '疲れ気味なので、早めに休む予定です。']
        detail_poor_choices = ['頭痛がするため、こまめに休憩を取りながら進めました。',
                               '少し体調を崩してしまったため、無理のない範囲で取り組みました。',
                               '倦怠感があるため、スタッフに相談して作業を調整しました。']

        # 4. 日ごとの勤怠・生活データの生成ループ
        current_date = start_date
        total_created = 0
        total_updated = 0

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

                at_home = random.choice([True, False])

                # 入室・退出時刻
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

                # 睡眠時間（models.pyのIntegerFieldに合わせて5〜9時間の整数値をランダム生成）
                sleep_hours = random.randint(5, 9)

                # 服薬チェックの3パターンをランダム選択
                med_pattern = random.choice(['all_true', 'some_false', 'all_false'])
                if med_pattern == 'all_true':
                    med_m, med_n, med_nig = True, True, True
                elif med_pattern == 'all_false':
                    med_m, med_n, med_nig = False, False, False
                else:
                    med_m = random.choice([True, False])
                    med_n = random.choice([True, False])
                    med_nig = random.choice([True, False])
                    if med_m and med_n and med_nig:
                        med_nig = False

                # 体調と体調詳細モーダル
                condition = random.choice(['〇', '△', '✕'])
                cond_detail_good = random.choice(detail_good_choices)
                cond_detail_caution = random.choice(detail_caution_choices)
                cond_detail_poor = random.choice(detail_poor_choices)

                # データベース保存用パラメータ
                defaults_data = {
                    'at_home': at_home,
                    'sleep_time_hours': sleep_hours,
                    'condition': condition,
                    'condition_detail_good': cond_detail_good,
                    'condition_detail_caution': cond_detail_caution,
                    'condition_detail_poor': cond_detail_poor,
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

                # idとuserの両方を検索条件に指定し、安全にレコードの重複を防ぎます
                input_screen, created = InputScreen.objects.update_or_create(
                    id=home_screen.id,
                    user=user,
                    defaults=defaults_data
                )

                input_screen.condition_detail_good = cond_detail_good
                input_screen.condition_detail_caution = cond_detail_caution
                input_screen.condition_detail_poor = cond_detail_poor
                input_screen.save()

                if created:
                    total_created += 1
                else:
                    total_updated += 1

            current_date += timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(f'処理が完了しました。新規作成: {total_created} 件, 更新: {total_updated} 件'))
