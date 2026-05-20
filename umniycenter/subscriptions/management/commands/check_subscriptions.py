from django.core.management.base import BaseCommand

from subscriptions.services import SubscriptionMonitoringService


class Command(BaseCommand):
    help = 'Checks subscriptions for expired dates, exhausted lessons and renewal risks.'

    def handle(self, *args, **options):
        result = SubscriptionMonitoringService.run_daily_check()
        self.stdout.write(self.style.SUCCESS('Subscription check completed'))
        self.stdout.write(f"Expired by date updated: {result['expired_updated']}")
        self.stdout.write(f"Exhausted by lessons updated: {result['exhausted_updated']}")
        self.stdout.write(f"Low lessons: {result['low_lessons']}")
        self.stdout.write(f"Expiring soon: {result['expiring_soon']}")
        self.stdout.write(f"Pending payment: {result['pending_payment']}")
        self.stdout.write(f"Negative balance: {result['negative_balance']}")
        self.stdout.write(f"Renewal tasks created: {result.get('tasks_created', 0)}")
