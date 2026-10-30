import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from transformers import pipeline
import re
from collections import Counter
import io
import requests
import sqlite3
import hashlib
from datetime import datetime

# =====================================
# SAYFA VE TEMA YAPILANDIRMASI
# =====================================
st.set_page_config(
    page_title="AI Müşteri Geri Bildirim Analitiği & BI",
    page_icon="🚀",
    layout="wide"
)

# Kurumsal Yüksek Kontrastlı Açık Tema
st.markdown("""
<style>
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
    }
    h1, h2, h3, h4, h5, h6, p, span, label {
        color: #0f172a !important;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        padding: 16px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="stMetricLabel"] p {
        color: #475569 !important;
        font-weight: 600;
        font-size: 14px;
    }
    div[data-testid="stMetricValue"] div {
        color: #0284c7 !important;
        font-weight: 700;
    }
    .stButton>button {
        background: linear-gradient(90deg, #2563eb 0%, #1d4ed8 100%);
        color: #ffffff !important;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 10px 20px;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #1d4ed8 0%, #1e40af 100%);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        color: #ffffff !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #e2e8f0;
        border-radius: 8px 8px 0px 0px;
        color: #334155 !important;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
    }
    .stTextInput input, .stTextArea textarea {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
    }
</style>
""", unsafe_allow_html=True)

# =====================================
# VERİTABANI VE KULLANICI YÖNETİMİ
# =====================================
def hash_sifre(sifre):
    return hashlib.sha256(sifre.encode("utf-8")).hexdigest()

def db_baslat():
    conn = sqlite3.connect("analiz_veritabani.db")
    c = conn.cursor()
    
    # Kullanıcılar Tablosu
    c.execute('''
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT UNIQUE,
            sifre_hash TEXT
        )
    ''')

    # Kullanıcıya Özel Rapor Tablosu
    c.execute('''
        CREATE TABLE IF NOT EXISTS gecmis_raporlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT,
            tarih TEXT,
            kaynak_adi TEXT,
            toplam_yorum INTEGER,
            olumlu_adet INTEGER,
            olumsuz_adet INTEGER,
            karisik_adet INTEGER,
            nps_skoru REAL,
            kriz_adet INTEGER
        )
    ''')

    # Eksik sütun kontrolü ve otomatik onarım
    c.execute("PRAGMA table_info(gecmis_raporlar)")
    sutunlar = [kolon[1] for kolon in c.fetchall()]
    if "kullanici_adi" not in sutunlar:
        c.execute("ALTER TABLE gecmis_raporlar ADD COLUMN kullanici_adi TEXT")

    # Varsayılan test kullanıcısı
    c.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", ("demo",))
    if not c.fetchone():
        c.execute('''
            INSERT INTO kullanicilar (kullanici_adi, sifre_hash)
            VALUES (?, ?)
        ''', ("demo", hash_sifre("123456")))

    conn.commit()
    conn.close()

def kullanici_kayit(kullanici_adi, sifre):
    try:
        conn = sqlite3.connect("analiz_veritabani.db")
        c = conn.cursor()
        c.execute('''
            INSERT INTO kullanicilar (kullanici_adi, sifre_hash)
            VALUES (?, ?)
        ''', (kullanici_adi.strip(), hash_sifre(sifre)))
        conn.commit()
        conn.close()
        return True, "Kayıt başarıyla tamamlandı! Giriş sekmesinden hesabınıza girebilirsiniz."
    except sqlite3.IntegrityError:
        return False, "Bu kullanıcı adı zaten alınmış!"
    except Exception as e:
        return False, f"Hata: {str(e)}"

def kullanici_giris(kullanici_adi, sifre):
    conn = sqlite3.connect("analiz_veritabani.db")
    c = conn.cursor()
    c.execute('''
        SELECT kullanici_adi FROM kullanicilar 
        WHERE kullanici_adi = ? AND sifre_hash = ?
    ''', (kullanici_adi.strip(), hash_sifre(sifre)))
    res = c.fetchone()
    conn.close()
    return res

def db_kaydet(kullanici_adi, kaynak, toplam, olumlu, olumsuz, karisik, nps, kriz):
    conn = sqlite3.connect("analiz_veritabani.db")
    c = conn.cursor()
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO gecmis_raporlar (kullanici_adi, tarih, kaynak_adi, toplam_yorum, olumlu_adet, olumsuz_adet, karisik_adet, nps_skoru, kriz_adet)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (kullanici_adi, simdi, kaynak, toplam, olumlu, olumsuz, karisik, nps, kriz))
    conn.commit()
    conn.close()

def db_getir(kullanici_adi):
    conn = sqlite3.connect("analiz_veritabani.db")
    df = pd.read_sql_query(
        "SELECT id, tarih, kaynak_adi, toplam_yorum, olumlu_adet, olumsuz_adet, karisik_adet, nps_skoru, kriz_adet FROM gecmis_raporlar WHERE kullanici_adi = ? ORDER BY id DESC", 
        conn, 
        params=(kullanici_adi,)
    )
    conn.close()
    return df

db_baslat()

# =====================================
# GİRİŞ / KAYIT EKRANI (REACT FORMU İLE KORUNMUŞ)
# =====================================
if "giris_yapildi" not in st.session_state:
    st.session_state["giris_yapildi"] = False

if not st.session_state["giris_yapildi"]:
    st.title("🔒 AI Müşteri Analitiği - Kullanıcı Girişi")
    st.caption("Hesabınıza giriş yapın veya yeni bir hesap oluşturun.")
    st.divider()

    auth_tab1, auth_tab2 = st.tabs(["🔑 Giriş Yap", "📝 Kayıt Ol"])

    with auth_tab1:
        st.subheader("Giriş Yap")
        with st.form("form_giris"):
            k_adi = st.text_input("Kullanıcı Adı:", placeholder="demo")
            k_sifre = st.text_input("Şifre:", type="password", placeholder="123456")
            giris_butonu = st.form_submit_button("🚀 Giriş Yap", use_container_width=True)

            if giris_butonu:
                if k_adi and k_sifre:
                    kullanici = kullanici_giris(k_adi, k_sifre)
                    if kullanici:
                        st.session_state["giris_yapildi"] = True
                        st.session_state["kullanici_adi"] = kullanici[0]
                        st.success(f"Hoş geldiniz, {kullanici[0]}!")
                        st.rerun()
                    else:
                        st.error("Kullanıcı adı veya şifre hatalı!")
                else:
                    st.warning("Lütfen kullanıcı adı ve şifrenizi girin.")

        st.info("💡 Test Kullanıcısı: Kullanıcı Adı: **demo** | Şifre: **123456**")

    with auth_tab2:
        st.subheader("Yeni Hesap Oluştur")
        with st.form("form_kayit"):
            y_kullanici = st.text_input("Kullanıcı Adı Seçin:", placeholder="kullanici123")
            y_sifre = st.text_input("Şifre Belirleyin:", type="password")
            y_sifre_tekrar = st.text_input("Şifre Tekrar:", type="password")
            kayit_butonu = st.form_submit_button("📝 Kaydı Tamamla", use_container_width=True)

            if kayit_butonu:
                if not y_kullanici or not y_sifre or not y_sifre_tekrar:
                    st.warning("Lütfen tüm alanları doldurun.")
                elif len(y_sifre) < 4:
                    st.error("Şifre en az 4 karakter olmalıdır.")
                elif y_sifre != y_sifre_tekrar:
                    st.error("Girdiğiniz şifreler birbiriyle eşleşmiyor!")
                else:
                    ok, msg = kullanici_kayit(y_kullanici, y_sifre)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

    st.stop()

# =====================================
# YAN PANEL & OTURUM BİLGİSİ
# =====================================
with st.sidebar:
    st.markdown("### 👤 Aktif Kullanıcı")
    st.write(f"**Kullanıcı Adı:** `{st.session_state['kullanici_adi']}`")
    st.caption("Verileriniz hesabınıza özel olarak izole edilmiştir.")
    st.divider()
    if st.button("🚪 Güvenli Çıkış Yap", use_container_width=True):
        st.session_state["giris_yapildi"] = False
        st.session_state.clear()
        st.rerun()

# =====================================
# ANA BAŞLIK
# =====================================
st.title("🚀 Enterprise Müşteri İçgörü Platformu")
st.caption(f"Aktif Oturum: {st.session_state['kullanici_adi']} | Güvenli & Bağımsız Çalışma Alanı")
st.divider()

# =====================================
# MODEL YÜKLEME
# =====================================
@st.cache_resource
def modeli_yukle():
    return pipeline(
        "sentiment-analysis",
        model="savasy/bert-base-turkish-sentiment-cased",
        device=-1
    )

# =====================================
# KÖK VE KURAL MOTORU
# =====================================
KESIN_OLUMSUZ_KOKLER = [
    "kötü", "berbat", "rezalet", "bozuk", "kırık", "çöp", "iade", 
    "beğenme", "memnun kalma", "alma", "tavsiye etme", "yavaş", 
    "hasar", "defolu", "çirkin", "geç geldi", "gecik", "gelmedi", 
    "ulaşmadı", "ezik", "parçalanmış", "pişman", "berbattı"
]

KESIN_OLUMLU_KOKLER = [
    "iyi", "güzel", "harika", "mükemmel", "süper", "muhteşem", "başarılı", 
    "kalite", "beğen", "memnun", "tavsiye ed", "kusursuz", "bayıl", 
    "şahane", "hızlı", "zamanında", "sağlam", "özenli", "teşekkür"
]

NOTR_IFADELER = [
    "normal", "fena değil", "idare eder", "orta", "ortalama", 
    "ne iyi ne kötü", "standart", "standard", "şöyle böyle", "eh işte"
]

KRIZ_KELIMELERI = [
    "dava", "mahkeme", "avukat", "tüketici hakem", "dolandırıcı", "sahtekar", 
    "hırsız", "zehirlen", "sahte ürün", "savcılık", "şikayetvar", "polise", "tüketici mahkemesi"
]

RENK_HARITASI = {
    "Olumlu": "#16a34a",
    "Olumsuz": "#dc2626",
    "Karışık": "#d97706",
    "Nötr": "#64748b"
}

def departman_tespit_et(metin):
    m = metin.lower()
    if any(k in m for k in ["kargo", "teslim", "paket", "kurye", "ulaş", "kutusu"]):
        return "Kargo & Teslimat"
    if any(k in m for k in ["fiyat", "ücret", "pahalı", "ucuz", "para", "değer"]):
        return "Fiyat & Değer"
    if any(k in m for k in ["müşteri hizmet", "destek", "temsilci", "satıcı"]):
        return "Müşteri Hizmetleri"
    return "Ürün Kalitesi"

def duygu_skorla_kural(metin):
    m = metin.lower().strip()
    if "istediğim gibi" in m or "görseldeki gibi" in m or "beklediğim gibi" in m:
        if not any(o in m for o in KESIN_OLUMSUZ_KOKLER):
            return "Olumlu", 98.0

    for n in NOTR_IFADELER:
        if n in m:
            return "Nötr", 90.0
    if " gibi" in m and not any(ol in m for ol in KESIN_OLUMLU_KOKLER):
        return "Nötr", 90.0

    for o in KESIN_OLUMSUZ_KOKLER:
        if o in m:
            return "Olumsuz", 98.0

    for ol in KESIN_OLUMLU_KOKLER:
        if ol in m:
            return "Olumlu", 98.0

    return None, None

def tekil_kesit_analiz_et(kesit, model):
    d, g = duygu_skorla_kural(kesit)
    if d is not None:
        return d, g
    try:
        tahmin = model(kesit, truncation=True, max_length=512)[0]
        label = str(tahmin.get("label", "")).strip().lower()
        skor = round(float(tahmin.get("score", 0.0)) * 100, 2)
        if "label_0" in label or "pos" in label:
            return "Olumlu", skor
        elif "label_1" in label or "neg" in label:
            return "Olumsuz", skor
        else:
            return "Nötr", skor
    except Exception:
        return "Nötr", 0.0

def metni_analiz_et(metin, model):
    ham = str(metin).strip()
    if not ham:
        return {"genel_duygu": "Nötr", "genel_guven": 0.0, "genel_kategori": "Genel", "detaylar": [], "kriz": False}

    kriz_mi = any(k in ham.lower() for k in KRIZ_KELIMELERI)
    ayirici_desen = r'\s+(?:ama|fakat|ancak|lakin|ve|hem de)\s+|[,;]'
    ham_parcalar = re.split(ayirici_desen, ham, flags=re.IGNORECASE)
    parcalar = [p.strip() for p in ham_parcalar if len(p.strip()) > 1]
    if not parcalar:
        parcalar = [ham]

    detaylar = []
    for p in parcalar:
        d, g = tekil_kesit_analiz_et(p, model)
        kat = departman_tespit_et(p)
        detaylar.append({"kategori": kat, "duygu": d, "guven": g, "kesit": p})

    olumlu = any(d["duygu"] == "Olumlu" for d in detaylar)
    olumsuz = any(d["duygu"] == "Olumsuz" for d in detaylar)

    if olumlu and olumsuz:
        genel_d = "Karışık"
    elif olumsuz:
        genel_d = "Olumsuz"
    elif olumlu:
        genel_d = "Olumlu"
    else:
        genel_d = "Nötr"

    tum_kat = " / ".join(list(dict.fromkeys(d["kategori"] for d in detaylar)))
    ort_guven = round(sum(d["guven"] for d in detaylar) / len(detaylar), 2)

    return {
        "genel_duygu": genel_d,
        "genel_guven": ort_guven,
        "genel_kategori": tum_kat,
        "detaylar": detaylar,
        "kriz": kriz_mi
    }

def batch_analiz_et(metin_listesi, model, batch_boyutu=32):
    sonuclar = []
    toplam = len(metin_listesi)
    ilerleme_cubugu = st.progress(0, text="Yorumlar toplu işleniyor...")

    for i in range(0, toplam, batch_boyutu):
        parti = metin_listesi[i:i + batch_boyutu]
        for metin in parti:
            sonuclar.append(metni_analiz_et(metin, model))
        ilerleme = min((i + batch_boyutu) / toplam, 1.0)
        ilerleme_cubugu.progress(ilerleme, text=f"İşleniyor: {min(i + batch_boyutu, toplam)} / {toplam}")

    ilerleme_cubugu.empty()
    return sonuclar

def basit_web_yorumlari_cek(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        yanit = requests.get(url, headers=headers, timeout=10)
        if yanit.status_code != 200:
            return None, f"Sayfa yüklenemedi. HTTP Durum Kodu: {yanit.status_code}"

        metin_parcalari = re.findall(r'<(?:p|span)[^>]*>(.*?)</(?:p|span)>', yanit.text, re.IGNORECASE | re.DOTALL)
        temiz_yorumlar = []
        for m in metin_parcalari:
            temiz = re.sub(r'<[^>]+>', '', m).strip()
            if 20 < len(temiz) < 400 and temiz not in temiz_yorumlar:
                temiz_yorumlar.append(temiz)

        if not temiz_yorumlar:
            return None, "Sayfadan otomatik yorum alınamadı. 'Ham Metin Yapıştır' seçeneğini kullanabilirsiniz."

        return pd.DataFrame({"Yorumlar": temiz_yorumlar[:60]}), None
    except Exception as e:
        return None, f"Hata: {str(e)}"

def yanit_taslagi_uret(departman, kesit):
    if departman == "Kargo & Teslimat":
        return f"Değerli Müşterimiz,\n\nSiparişinizin teslimat sürecinde yaşanan aksaklıktan ({kesit}) dolayı içtenlikle özür dileriz. Kargo iş ortağımız nezdinde aksiyon alınmıştır.\n\nSaygılarımızla,\nMüşteri Deneyimi Ekibi"
    elif departman == "Ürün Kalitesi":
        return f"Değerli Müşterimiz,\n\nÜrünümüzle ilgili belirttiğiniz olumsuzluk ({kesit}) kalite ekiplerimize aktarılmıştır. Memnuniyetiniz adına koşulsuz iade ve değişim hakkınız saklıdır.\n\nSaygılarımızla,\nKalite Güvence Birimi"
    elif departman == "Fiyat & Değer":
        return f"Değerli Müşterimiz,\n\nFiyat ve fayda dengesi konusundaki geri bildiriminiz için teşekkür ederiz. Sonraki siparişinizde geçerli indirim kuponunuz tanımlanmıştır.\n\nSaygılarımızla,\nSatış Ekibi"
    else:
        return f"Değerli Müşterimiz,\n\nYaşadığınız durum için üzgünüz. Temsilcimiz en kısa sürede doğrudan sizinle iletişime geçecektir.\n\nSaygılarımızla,\nDestek Birimi"

# =====================================
# SEKME YAPISI
# =====================================
sekme1, sekme2, sekme3, sekme4 = st.tabs([
    "📊 Dosya Analizi & BI", 
    "🌐 Evrensel Ürün Yorum Çekici", 
    "🧪 Canlı Tekil Test & Auto-Reply", 
    f"📜 {st.session_state['kullanici_adi']} Arşivi (İzole DB)"
])

# --------------------------------------------------
# SEKME 1: DOSYA ANALİZİ
# --------------------------------------------------
with sekme1:
    dosya = st.file_uploader("CSV veya Excel dosyanızı yükleyin:", type=["csv", "xlsx"])
    if dosya is not None:
        try:
            if dosya.name.lower().endswith(".csv"):
                icerik = dosya.getvalue().decode("utf-8-sig", errors="ignore").splitlines()
                satirlar = [s.strip().lstrip("•").strip() for s in icerik if s.strip()]
                if len(satirlar) > 0 and ("kategori" not in satirlar[0].lower() and "yorum" not in satirlar[0].lower()):
                    df = pd.DataFrame({"Yorumlar": satirlar})
                else:
                    df = pd.read_csv(io.StringIO("\n".join(satirlar)), on_bad_lines="skip")
            else:
                df = pd.read_excel(dosya)

            st.write("### 📄 Dosya Önizlemesi")
            st.dataframe(df.head(3), use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                sutun = st.selectbox("Yorumların bulunduğu sütun:", df.columns, key="secilen_sutun")
            with c2:
                tarih_adaylari = ["Yok"] + [col for col in df.columns if any(t in col.lower() for t in ["tarih", "date", "time", "gün"])]
                tarih_sutunu = st.selectbox("Tarih sütunu (opsiyonel trend analizi):", tarih_adaylari)

            if st.button("🚀 Toplu Analizi Başlat", use_container_width=True):
                model = modeli_yukle()
                tum_metinler = df[sutun].astype(str).tolist()
                
                analiz_sonuclari = batch_analiz_et(tum_metinler, model)

                res_df = df.copy()
                res_df["Kategori"] = [r["genel_kategori"] for r in analiz_sonuclari]
                res_df["Duygu"] = [r["genel_duygu"] for r in analiz_sonuclari]
                res_df["Güven (%)"] = [r["genel_guven"] for r in analiz_sonuclari]
                res_df["Kriz Riski"] = ["🚨 Acil Risk" if r["kriz"] else "Normal" for r in analiz_sonuclari]

                toplam = len(res_df)
                olumlu_sayi = int((res_df["Duygu"] == "Olumlu").sum())
                olumsuz_sayi = int((res_df["Duygu"] == "Olumsuz").sum())
                karisik_sayi = int((res_df["Duygu"] == "Karışık").sum())
                kriz_sayi = int((res_df["Kriz Riski"] == "🚨 Acil Risk").sum())
                nps_skoru = round(((olumlu_sayi - olumsuz_sayi) / toplam) * 100, 1) if toplam else 0.0

                st.session_state["analiz_sonuc_df"] = res_df
                st.session_state["nps_skoru"] = nps_skoru

                db_kaydet(st.session_state["kullanici_adi"], dosya.name, toplam, olumlu_sayi, olumsuz_sayi, karisik_sayi, nps_skoru, kriz_sayi)
                st.success(f"Analiz tamamlandı ve {st.session_state['kullanici_adi']} arşivine kaydedildi!")

            if "analiz_sonuc_df" in st.session_state and st.session_state["analiz_sonuc_df"] is not None:
                sonuc_df = st.session_state["analiz_sonuc_df"]
                nps = st.session_state.get("nps_skoru", 0.0)
                st.divider()

                kriz_kayitlari = sonuc_df[sonuc_df["Kriz Riski"] == "🚨 Acil Risk"]
                if not kriz_kayitlari.empty:
                    st.error(f"🚨 **DİKKAT: {len(kriz_kayitlari)} adet kriz riski taşıyan acil yorum tespit edildi!**")
                    with st.expander("🔴 Kriz Riski Taşıyan Yorumlar Listesi", expanded=True):
                        st.dataframe(kriz_kayitlari[[sutun, "Kategori", "Duygu", "Kriz Riski"]], use_container_width=True)

                m1, m2, m3, m4, m5 = st.columns(5)
                toplam = len(sonuc_df)
                olumlu_sayi = int((sonuc_df["Duygu"] == "Olumlu").sum())
                olumsuz_sayi = int((sonuc_df["Duygu"] == "Olumsuz").sum())
                karisik_sayi = int((sonuc_df["Duygu"] == "Karışık").sum())

                m1.metric("😊 Olumlu", olumlu_sayi)
                m2.metric("😞 Olumsuz", olumsuz_sayi)
                m3.metric("🔀 Karışık", karisik_sayi)
                m4.metric("🏆 NPS Skoru", f"{nps}")
                m5.metric("📊 Toplam Kayıt", toplam)

                st.write("")

                g1, g2, g3 = st.columns([1, 1, 1])
                with g1:
                    st.subheader("📈 Duygu Oranları")
                    duygu_ozet = sonuc_df["Duygu"].value_counts().reset_index()
                    duygu_ozet.columns = ["Duygu", "Adet"]
                    fig_duygu = px.pie(
                        duygu_ozet, names="Duygu", values="Adet", hole=0.45,
                        color="Duygu", color_discrete_map=RENK_HARITASI
                    )
                    fig_duygu.update_layout(template="plotly_white", margin=dict(t=20, b=20, l=20, r=20))
                    st.plotly_chart(fig_duygu, use_container_width=True)

                with g2:
                    st.subheader("🏷️ Departman Dağılımı")
                    kat_duygu = sonuc_df.groupby(["Kategori", "Duygu"]).size().reset_index(name="Adet")
                    fig_kat = px.bar(
                        kat_duygu, x="Kategori", y="Adet", color="Duygu", barmode="stack",
                        color_discrete_map=RENK_HARITASI
                    )
                    fig_kat.update_layout(template="plotly_white", margin=dict(t=20, b=20, l=20, r=20))
                    st.plotly_chart(fig_kat, use_container_width=True)

                with g3:
                    st.subheader("🎯 NPS İbre Göstergesi")
                    fig_gauge = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=nps,
                        domain={'x': [0, 1], 'y': [0, 1]},
                        gauge={
                            'axis': {'range': [-100, 100]},
                            'bar': {'color': "#0284c7"},
                            'steps': [
                                {'range': [-100, 0], 'color': "#fee2e2"},
                                {'range': [0, 50], 'color': "#fef3c7"},
                                {'range': [50, 100], 'color': "#dcfce7"}
                            ]
                        }
                    ))
                    fig_gauge.update_layout(template="plotly_white", height=320)
                    st.plotly_chart(fig_gauge, use_container_width=True)

                st.subheader("📋 Analiz Edilen Yorum Tablosu")
                st.dataframe(sonuc_df.drop(columns=["_tarih_parse"], errors="ignore"), use_container_width=True)

                csv_cikti = sonuc_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("📥 CSV Raporunu İndir", data=csv_cikti, file_name="kullanici_analiz_raporu.csv", mime="text/csv", use_container_width=True)

        except Exception as e:
            st.error(f"Hata: {e}")

# --------------------------------------------------
# SEKME 2: EVRENSEL ÜRÜN YORUM ÇEKİCİ
# --------------------------------------------------
with sekme2:
    st.subheader("🌐 Evrensel Ürün Yorum Çekici")
    st.write("Herhangi bir ürün sayfasının linkini girin veya yorum metnini kutuya yapıştırın.")

    giris_turu = st.radio("Veri Giriş Yöntemi:", ["🔗 Web Sitesi / Ürün Linki ile Çek", "📝 Toplu Yorum Metnini Kutuya Yapıştır"], horizontal=True)

    metinler_listesi = []

    if giris_turu == "🔗 Web Sitesi / Ürün Linki ile Çek":
        urun_url = st.text_input("Ürün veya İnceleme Sayfası Bağlantısı:", placeholder="https://www.ornek-site.com/urun-sayfasi")
        if st.button("🌐 Sayfadan Yorumları Otomatik Çıkar ve Analiz Et", use_container_width=True):
            if urun_url.strip():
                with st.spinner("Web sayfası taranıyor..."):
                    cekilen_df, hata = basit_web_yorumlari_cek(urun_url)
                    if hata:
                        st.warning(hata)
                    else:
                        metinler_listesi = cekilen_df["Yorumlar"].tolist()
                        st.success(f"{len(metinler_listesi)} adet yorum bloğu ayıklandı!")
            else:
                st.warning("Lütfen bir web adresi girin.")
    else:
        yapistirilan_metin = st.text_area(
            "Yorumları satır satır yapıştırın:",
            height=150,
            placeholder="1. yorum: Ürün çok kaliteli tavsiye ederim\n2. yorum: Kargo 5 günde geldi çok yavaş"
        )
        if st.button("📋 Yapıştırılan Yorumları Analiz Et", use_container_width=True):
            if yapistirilan_metin.strip():
                metinler_listesi = [satir.strip().lstrip("•-0123456789. ") for satir in yapistirilan_metin.splitlines() if len(satir.strip()) > 3]
            else:
                st.warning("Lütfen metin kutusuna yorum yapıştırın.")

    if metinler_listesi:
        model = modeli_yukle()
        analizler = batch_analiz_et(metinler_listesi, model)

        web_df = pd.DataFrame({
            "Yorum": metinler_listesi,
            "Kategori": [r["genel_kategori"] for r in analizler],
            "Duygu": [r["genel_duygu"] for r in analizler],
            "Güven (%)": [r["genel_guven"] for r in analizler],
            "Kriz Riski": ["🚨 Acil Risk" if r["kriz"] else "Normal" for r in analizler]
        })

        st.divider()
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            fig_w_pie = px.pie(web_df, names="Duygu", color="Duygu", color_discrete_map=RENK_HARITASI, hole=0.4)
            fig_w_pie.update_layout(template="plotly_white")
            st.plotly_chart(fig_w_pie, use_container_width=True)
        with col_w2:
            fig_w_bar = px.bar(web_df.groupby(["Kategori", "Duygu"]).size().reset_index(name="Adet"), x="Kategori", y="Adet", color="Duygu", color_discrete_map=RENK_HARITASI)
            fig_w_bar.update_layout(template="plotly_white")
            st.plotly_chart(fig_w_bar, use_container_width=True)

        st.dataframe(web_df, use_container_width=True)

# --------------------------------------------------
# SEKME 3: TEKİL TEST & OTOMATİK YANIT
# --------------------------------------------------
with sekme3:
    st.subheader("🧪 Canlı Tekil Cümle Testi & Temsilci Yanıt Motoru")
    canli_metin = st.text_area("Müşteri yorumu:", placeholder="Örn: ürünün kalitesi harika ama kargosu çok gecikti, dava edeceğim")

    if st.button("🚀 Tekil Yorumu Ayrıştır", use_container_width=True):
        if canli_metin.strip():
            with st.spinner("Model çözümlüyor..."):
                model = modeli_yukle()
                sonuc = metni_analiz_et(canli_metin, model)

                if sonuc["kriz"]:
                    st.error("🚨 **KRİTİK UYARI:** Hukuki veya itibar riski tespit edildi!")

                st.markdown(f"### 📌 Genel Duygu Durumu: **{sonuc['genel_duygu']}** (Ortalama Güven: %{sonuc['genel_guven']})")

                detaylar = sonuc["detaylar"]
                sutunlar = st.columns(len(detaylar))
                olumsuzlar = []

                for i, d in enumerate(detaylar):
                    with sutunlar[i]:
                        if d["duygu"] == "Olumlu":
                            st.success(f"### 😊 {d['kategori']}\n**Durum:** OLUMLU  \n**Güven:** %{d['guven']}")
                        elif d["duygu"] == "Olumsuz":
                            st.error(f"### 😞 {d['kategori']}\n**Durum:** OLUMSUZ  \n**Güven:** %{d['guven']}")
                            olumsuzlar.append(d)
                        else:
                            st.warning(f"### 😐 {d['kategori']}\n**Durum:** NÖTR  \n**Güven:** %{d['guven']}")
                        st.caption(f'Kesit: *"{d["kesit"]}"*')

                if olumsuzlar:
                    st.divider()
                    st.subheader("✉️ Müşteri Destek İçin Hazır Şablonlar")
                    for op in olumsuzlar:
                        taslak = yanit_taslagi_uret(op["kategori"], op["kesit"])
                        st.text_area(f"📋 {op['kategori']} Yanıt Metni:", value=taslak, height=130)
        else:
            st.warning("Lütfen bir yorum yazın.")

# --------------------------------------------------
# SEKME 4: ANALİZ ARŞİVİ (KULLANICIYA ÖZEL İZOLE SQLITE)
# --------------------------------------------------
with sekme4:
    st.subheader(f"📜 {st.session_state['kullanici_adi']} Analiz Arşivi")
    st.caption("Yalnızca sizin hesabınız üzerinden yapılmış olan analizler listelenmektedir.")
    gecmis_df = db_getir(st.session_state["kullanici_adi"])
    if not gecmis_df.empty:
        st.dataframe(gecmis_df, use_container_width=True)
    else:
        st.info("Hesabınıza ait henüz kaydedilmiş geçmiş bir analiz bulunmamaktadır.")