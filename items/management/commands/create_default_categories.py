from django.core.management.base import BaseCommand
from items.models import ItemCategory

class Command(BaseCommand):
    help = 'Varsayılan kategorileri oluşturur'

    def handle(self, *args, **options):
        default_categories = [
            {"name": "Elektronik", "description": "Telefon, laptop, kulaklık vb. elektronik cihazlar", "icon": "📱"},
            {"name": "Kişisel Eşya", "description": "Cüzdan, çanta, anahtarlık vb. kişisel eşyalar", "icon": "👝"},
            {"name": "Kitap & Kırtasiye", "description": "Kitaplar, defterler, kalemler vb.", "icon": "📚"},
            {"name": "Giyim", "description": "Kıyafetler, ayakkabılar, aksesuarlar", "icon": "👕"},
            {"name": "Spor Ekipmanı", "description": "Spor malzemeleri, ekipmanları", "icon": "⚽"},
            {"name": "Diğer", "description": "Diğer kategorilere uymayan eşyalar", "icon": "📦"},
        ]
        
        created_count = 0
        existing_count = 0
        
        for category_data in default_categories:
            category, created = ItemCategory.objects.get_or_create(
                name=category_data["name"],
                defaults={
                    "description": category_data["description"],
                    "icon": category_data["icon"]
                }
            )
            
            if created:
                created_count += 1
            else:
                existing_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'{created_count} adet yeni kategori oluşturuldu, {existing_count} adet kategori zaten mevcuttu.'
            )
        )