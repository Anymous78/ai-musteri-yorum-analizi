# 🚀 AI Destekli Müşteri Geri Bildirim Analitiği & BI Platformu

Bu proje, Türkçe e-ticaret ve müşteri geri bildirimlerini derinlemesine analiz eden, makine öğrenimi (BERT) ve kural tabanlı hibrit bir mimariye sahip kurumsal bir SaaS analitik platformudur.

## 📌 Temel Özellikler
- **Hibrit Duygu Analizi:** `savasy/bert-base-turkish-sentiment-cased` BERT modeli ile özel kural/sözlük motorunun entegre çalışması.
- **Departman Sınıflandırma:** Yorumları Kargo, Ürün Kalitesi, Müşteri Hizmetleri ve Fiyat/Değer kategorilerine otomatik ayrıştırma.
- **Kriz Radarı:** Hukuki risk ve itibar tehdidi taşıyan yorumları anlık olarak filtreleme.
- **NPS (Net Promoter Score) İbresi:** Müşteri memnuniyetini -100 ile +100 arasında dinamik ölçümleme.
- **Çoklu Kullanıcı & SQLite İzolasyonu:** SHA-256 şifreli kayıt/giriş sistemi ve her kullanıcıya özel geçmiş analiz arşivi.
- **Otomatik Temsilci Yanıtı:** Olumsuz bildirimlere yönelik departman bazlı hazır aksiyon şablonları.

## 🛠️ Kurulum ve Çalıştırma

1. Repoyu klonlayın veya indirin:
```bash
git clone [https://github.com/kullanici-adiniz/ai-musteri-yorum-analizi.git](https://github.com/kullanici-adiniz/ai-musteri-yorum-analizi.git)
cd ai-musteri-yorum-analizi