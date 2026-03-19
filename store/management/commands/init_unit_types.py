# store/management/commands/init_unit_types.py
from django.core.management.base import BaseCommand
from store.models import UnitType

class Command(BaseCommand):
    help = 'Инициализация типов единиц измерения'

    def handle(self, *args, **options):
        unit_types = [
            {'name': 'Штука', 'code': 'piece', 'short_name': 'шт'},
            {'name': 'Кубический метр', 'code': 'cubic', 'short_name': 'м³'},
            {'name': 'Квадратный метр', 'code': 'square', 'short_name': 'м²'},
            {'name': 'Упаковка', 'code': 'pack', 'short_name': 'уп'},
            {'name': 'Погонный метр', 'code': 'linear', 'short_name': 'п.м'},
        ]
        
        for unit_data in unit_types:
            unit, created = UnitType.objects.get_or_create(
                code=unit_data['code'],
                defaults={
                    'name': unit_data['name'],
                    'short_name': unit_data['short_name']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Создан тип: {unit.name}'))
            else:
                self.stdout.write(f'Тип уже существует: {unit.name}')
        
        self.stdout.write(self.style.SUCCESS('Инициализация завершена'))