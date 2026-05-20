from django.core.management.base import BaseCommand

from main.models import ParticipantRequest
from sales.models import Lead
from tasks.services import TaskService


class Command(BaseCommand):
    help = 'Creates Lead records for existing participant requests.'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        tasks_created = 0
        for participant_request in ParticipantRequest.objects.prefetch_related('courses').all():
            before_exists = hasattr(participant_request, 'lead')
            lead = Lead.from_participant_request(participant_request)
            if before_exists:
                updated += 1
            else:
                created += 1
            _, task_was_created = TaskService.create_for_lead(lead, assignee=lead.assigned_to)
            if task_was_created:
                tasks_created += 1
        self.stdout.write(self.style.SUCCESS(f'Lead sync completed. Created: {created}, existing: {updated}, tasks created: {tasks_created}'))
