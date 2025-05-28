// Ana DOM içeriği yüklendiğinde çalıştırılacak fonksiyonlar
document.addEventListener('DOMContentLoaded', function () {
  // Kaydırma olayını dinle ve header'ı güncelle
  window.addEventListener('scroll', function () {
    const header = document.querySelector('header');
    if (window.scrollY > 10) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
  });

  // Mesajlar için otomatik kapanma özelliği
  const messages = document.querySelectorAll('.message');
  messages.forEach(function (message) {
    // 5 saniye sonra mesajı kapat
    setTimeout(function () {
      message.style.opacity = '0';
      setTimeout(function () {
        message.style.display = 'none';
      }, 300);
    }, 5000);
  });

  // Aktif sayfa bağlantılarını vurgulama
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll('.nav-links a');

  navLinks.forEach(function (link) {
    const linkPath = link.getAttribute('href');
    if (linkPath === currentPath || (linkPath !== '/' && currentPath.startsWith(linkPath))) {
      link.classList.add('active');
    }
  });

  // Form gönderimlerinde yükleme göstergesi
  // NOT: .no-loading-indicator sınıfına sahip formları hariç tut
  const forms = document.querySelectorAll('form:not(.search-form):not(.no-loading-indicator)');
  forms.forEach(function (form) {
    form.addEventListener('submit', function (e) {
      const submitButton = form.querySelector('button[type="submit"]');
      if (submitButton) {
        const originalText = submitButton.innerHTML;
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner"></span> İşleniyor...';

        // Form gönderildikten 10 saniye sonra butonu eski haline getir (hata durumları için)
        setTimeout(function () {
          submitButton.disabled = false;
          submitButton.innerHTML = originalText;
        }, 10000);
      }
    });
  });

  // Kart görüntü efektleri
  const cards = document.querySelectorAll('.card');
  cards.forEach(function (card) {
    card.addEventListener('mouseenter', function () {
      const img = card.querySelector('.card-img');
      if (img) {
        img.style.transform = 'scale(1.05)';
      }
    });

    card.addEventListener('mouseleave', function () {
      const img = card.querySelector('.card-img');
      if (img) {
        img.style.transform = 'scale(1)';
      }
    });
  });

  // Tarih seçicileri için minimum tarih kontrolü
  const dateInputs = document.querySelectorAll('input[type="date"]');
  dateInputs.forEach(function (input) {
    // Eğer bu bir başlangıç tarihi ise, bugünün tarihini en küçük değer olarak ayarla
    if (input.id.includes('from') || input.name.includes('from')) {
      const today = new Date().toISOString().split('T')[0];
      input.min = today;
    }
  });

  // Arama formunu geliştir
  const searchForm = document.querySelector('.search-form');
  if (searchForm) {
    // Arama tipine göre görünür alanları değiştir
    const searchTypeSelect = searchForm.querySelector('select[name="search_type"]');
    if (searchTypeSelect) {
      const updateFormFields = function () {
        const searchType = searchTypeSelect.value;
        const lostFields = searchForm.querySelectorAll('.lost-only');
        const foundFields = searchForm.querySelectorAll('.found-only');

        if (searchType === 'lost') {
          lostFields.forEach(field => field.style.display = 'block');
          foundFields.forEach(field => field.style.display = 'none');
        } else if (searchType === 'found') {
          lostFields.forEach(field => field.style.display = 'none');
          foundFields.forEach(field => field.style.display = 'block');
        } else {
          lostFields.forEach(field => field.style.display = 'block');
          foundFields.forEach(field => field.style.display = 'block');
        }
      };

      searchTypeSelect.addEventListener('change', updateFormFields);
      // Sayfa yüklendiğinde de çalıştır
      updateFormFields();
    }
  }
});