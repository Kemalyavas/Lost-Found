# 🔍 Lost & Found System

A Django-based web application for managing lost and found items, helping reunite people with their lost belongings through a centralized platform.

## 📋 Overview

Lost & Found is a comprehensive web application built with Django that allows users to:
- Report lost items with detailed descriptions
- Post found items to help owners reclaim them
- Search and filter through listings
- Connect with item finders/owners
- Manage item status and updates

## ✨ Features

### Core Functionality
- **Item Management**: Create, read, update, and delete lost/found item listings
- **Search & Filter**: Advanced search with multiple filter options
- **Image Upload**: Attach photos to help identify items
- **User Authentication**: Secure user accounts and profiles
- **Status Tracking**: Track items from lost to found to claimed
- **Responsive Design**: Works seamlessly on desktop and mobile devices

### Additional Features
- Category-based organization
- Location-based filtering
- Date and time tracking
- Contact information management
- Admin dashboard for moderation

## 🛠️ Tech Stack

### Backend
- **Python 3.x**
- **Django 4.x** - Web framework
- **SQLite** - Database (Development)
- **Pillow** - Image processing

### Frontend
- **HTML5** - Structure
- **CSS3** - Styling
- **JavaScript** - Interactivity
- **Bootstrap** - UI Framework (if applicable)

## 📁 Project Structure

```
Lost-Found/
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── db.sqlite3            # SQLite database
├── items/                # Items app
│   ├── models.py         # Database models
│   ├── views.py          # View logic
│   ├── urls.py           # URL routing
│   ├── forms.py          # Form definitions
│   ├── admin.py          # Admin interface
│   └── templates/        # HTML templates
├── lostfound/            # Main project directory
│   ├── settings.py       # Project settings
│   ├── urls.py           # Main URL configuration
│   └── wsgi.py           # WSGI configuration
├── media/                # User uploaded files
├── static/               # Static files (CSS, JS, images)
└── templates/            # Base templates
```

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Step-by-Step Installation

1. **Clone the repository**
```bash
git clone https://github.com/Kemalyavas/Lost-Found.git
cd Lost-Found
```

2. **Create virtual environment**
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Apply database migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

5. **Create superuser (for admin access)**
```bash
python manage.py createsuperuser
```

6. **Collect static files**
```bash
python manage.py collectstatic
```

7. **Run development server**
```bash
python manage.py runserver
```

8. **Access the application**
- Main site: http://localhost:8000
- Admin panel: http://localhost:8000/admin

## ⚙️ Configuration

### Database Setup
By default, the project uses SQLite. For production, configure PostgreSQL or MySQL:

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Media Files Configuration
```python
# settings.py
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

### Email Configuration (for notifications)
```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-password'
```

## 📱 Usage

### For Users
1. **Register/Login**: Create an account or login
2. **Report Lost Item**: Fill out the lost item form with details
3. **Post Found Item**: Submit found items with photos and description
4. **Search Items**: Use filters to find your lost item
5. **Contact**: Reach out to the finder/owner
6. **Update Status**: Mark items as claimed when reunited

### For Admins
1. Access admin panel at `/admin`
2. Manage users and items
3. Moderate content
4. View statistics and reports

## 🔧 API Endpoints (if applicable)

```
GET    /api/items/          # List all items
POST   /api/items/          # Create new item
GET    /api/items/<id>/     # Get specific item
PUT    /api/items/<id>/     # Update item
DELETE /api/items/<id>/     # Delete item
GET    /api/items/search/   # Search items
```

## 🧪 Testing

Run tests with:
```bash
python manage.py test
```

For coverage report:
```bash
coverage run --source='.' manage.py test
coverage report
```

## 🚀 Deployment

### Heroku Deployment
1. Install Heroku CLI
2. Create `Procfile`:
```
web: gunicorn lostfound.wsgi
```

3. Configure environment variables
4. Deploy:
```bash
heroku create your-app-name
git push heroku main
heroku run python manage.py migrate
```

### Production Checklist
- [ ] Set `DEBUG = False`
- [ ] Configure proper database
- [ ] Set up static file serving
- [ ] Configure ALLOWED_HOSTS
- [ ] Set SECRET_KEY from environment
- [ ] Enable HTTPS
- [ ] Set up backup system

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

### Code Style
- Follow PEP 8 guidelines
- Write meaningful commit messages
- Add tests for new features
- Update documentation

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 👥 Authors

**Ali Kemal Yavaş**
- GitHub: [@Kemalyavas](https://github.com/Kemalyavas)
- LinkedIn: [Ali Kemal Yavaş](https://www.linkedin.com/in/alikemalyavas/)

## 🙏 Acknowledgments

- Django documentation and community
- Bootstrap for UI components
- Contributors and testers

## 📞 Support

For support, email kemalyavas@example.com or create an issue in the GitHub repository.

---

⭐ Star this repo if you like it!