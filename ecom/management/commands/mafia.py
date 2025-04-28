from django.core.management.base import BaseCommand
from ecom.mafia.mafia_algorithm import run_mafia

class Command(BaseCommand):
    help = 'Chạy thuật toán MAFIA: từ DB Order hoặc file CSV.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min_support',
            type=int,
            default=100,
            help='Ngưỡng support tối thiểu'
        )
        parser.add_argument(
            '--csv',
            type=str,
            help='Đường dẫn file CSV (nếu muốn dùng CSV thay vì DB)'
        )

    def handle(self, *args, **options):
        min_sup = options['min_support']
        csv_path = options.get('csv')

        source = f"CSV {csv_path}" if csv_path else "DB Orders"
        self.stdout.write(f'Chạy MAFIA (min_support={min_sup}) từ {source}...')

        itemsets = run_mafia(min_sup, csv_path)
        self.stdout.write(self.style.SUCCESS('Maximal frequent itemsets:'))
        for s in itemsets:
            self.stdout.write(f'  • {sorted(s)}')