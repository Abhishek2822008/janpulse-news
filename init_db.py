"""
JanPulse Database Initialization and Seeding Script
Executes schema.sql and populates sample categories, locations, tags, admin & user accounts,
and comprehensive bilingual news articles.
"""

import os
import sys
import pymysql
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from config import Config

def init_database():
    print(f"Connecting to MySQL at {Config.DB_HOST}:{Config.DB_PORT} as {Config.DB_USER}...")
    
    # 1. Connect without specific DB to create database if not exists
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        charset='utf8mb4'
    )
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            print(f"Database `{Config.DB_NAME}` verified/created.")
        conn.commit()
    finally:
        conn.close()

    # 2. Connect to the database and run schema.sql
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        schema_path = os.path.join(Config.BASE_DIR, 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Split statements by semicolon
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        with conn.cursor() as cursor:
            for stmt in statements:
                if stmt.upper().startswith('CREATE DATABASE') or stmt.upper().startswith('USE '):
                    continue
                cursor.execute(stmt)
        conn.commit()
        print("Schema tables initialized successfully.")

        # 3. Seed Users (Admin & Normal User)
        with conn.cursor() as cursor:
            # Check if admin already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", ('admin@janpulse.com',))
            admin = cursor.fetchone()
            if not admin:
                admin_pw_hash = generate_password_hash('Admin@JanPulse2026', method='scrypt')
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, role, is_super_admin, branch, avatar, is_active)
                    VALUES (%s, %s, %s, 'admin', 1, 'Headquarters / All', %s, 1)
                """, ('Chief Editor', 'admin@janpulse.com', admin_pw_hash, 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150'))
                admin_id = cursor.lastrowid
                print(f"Created Admin account: admin@janpulse.com / Admin@JanPulse2026 (ID: {admin_id})")
            else:
                admin_id = admin['id']

            # Check if test user exists
            cursor.execute("SELECT id FROM users WHERE email = %s", ('rahul@example.com',))
            user = cursor.fetchone()
            if not user:
                user_pw_hash = generate_password_hash('User@JanPulse2026', method='scrypt')
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, role, avatar, is_active)
                    VALUES (%s, %s, %s, 'user', %s, 1)
                """, ('Rahul Sharma', 'rahul@example.com', user_pw_hash, 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150'))
                user_id = cursor.lastrowid
                print(f"Created Test User: rahul@example.com / User@JanPulse2026 (ID: {user_id})")
            else:
                user_id = user['id']

        # 4. Seed Categories
        categories_data = [
            ('Latest News', 'ताज़ा ख़बरें', 'latest-news', 'Real-time updates and breaking developments from all fields'),
            ('Breaking News', 'ब्रेकिंग न्यूज़', 'breaking-news', 'Crucial breaking headlines and emergency alerts'),
            ('Local News', 'स्थानीय समाचार', 'local-news', 'Hyper-local news categorized by State, District, and City'),
            ('India', 'भारत', 'india', 'National affairs, government initiatives, and nationwide reports'),
            ('World', 'विदेश', 'world', 'Global geopolitics, international relations, and overseas news'),
            ('Politics', 'राजनीति', 'politics', 'Elections, parliamentary debates, party developments, and policies'),
            ('Business', 'व्यापार', 'business', 'Stock markets, economy, finance, startups, and industry analysis'),
            ('Technology', 'तकनीक', 'technology', 'AI advancements, smartphones, cybersecurity, and space missions'),
            ('Sports', 'खेल', 'sports', 'Cricket, football, badminton, Olympics, and tournament highlights'),
            ('Entertainment', 'मनोरंजन', 'entertainment', 'Cinema, OTT releases, celebrities, culture, and arts'),
            ('Health', 'स्वास्थ्य', 'health', 'Medical discoveries, wellness, nutrition, fitness, and healthcare policies')
        ]

        cat_id_map = {}
        with conn.cursor() as cursor:
            for name_en, name_hi, slug, desc in categories_data:
                cursor.execute("SELECT id FROM categories WHERE slug = %s", (slug,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("""
                        INSERT INTO categories (name_en, name_hi, slug, description)
                        VALUES (%s, %s, %s, %s)
                    """, (name_en, name_hi, slug, desc))
                    cat_id_map[slug] = cursor.lastrowid
                else:
                    cat_id_map[slug] = row['id']
        conn.commit()
        print(f"Seeded {len(cat_id_map)} categories.")

        # 5. Seed Locations (State -> District -> City)
        locations_data = [
            # Uttar Pradesh
            ('Uttar Pradesh', 'Lucknow', 'Lucknow Central'),
            ('Uttar Pradesh', 'Lucknow', 'Gomti Nagar'),
            ('Uttar Pradesh', 'Varanasi', 'Kashi City'),
            ('Uttar Pradesh', 'Kanpur', 'Kanpur Nagar'),
            ('Uttar Pradesh', 'Gautam Buddha Nagar', 'Noida'),
            # Maharashtra
            ('Maharashtra', 'Mumbai', 'South Mumbai'),
            ('Maharashtra', 'Mumbai', 'Bandra Suburban'),
            ('Maharashtra', 'Pune', 'Shivaji Nagar'),
            ('Maharashtra', 'Nagpur', 'Nagpur City'),
            # Delhi
            ('Delhi', 'New Delhi', 'Connaught Place'),
            ('Delhi', 'South Delhi', 'Hauz Khas'),
            ('Delhi', 'North Delhi', 'Civil Lines'),
            # Bihar
            ('Bihar', 'Patna', 'Patna Central'),
            ('Bihar', 'Gaya', 'Bodh Gaya'),
            ('Bihar', 'Muzaffarpur', 'Muzaffarpur City'),
            # Karnataka
            ('Karnataka', 'Bengaluru Urban', 'Electronic City'),
            ('Karnataka', 'Bengaluru Urban', 'Indiranagar'),
            ('Karnataka', 'Mysuru', 'Mysuru City'),
            # Rajasthan
            ('Rajasthan', 'Jaipur', 'Pink City Central'),
            ('Rajasthan', 'Jodhpur', 'Jodhpur Heritage'),
            ('Rajasthan', 'Udaipur', 'Lake City'),
            # Gujarat
            ('Gujarat', 'Ahmedabad', 'SG Highway'),
            ('Gujarat', 'Surat', 'Diamond City'),
            # West Bengal
            ('West Bengal', 'Kolkata', 'Salt Lake'),
            ('West Bengal', 'Howrah', 'Howrah Station Area')
        ]

        location_id_map = {}
        with conn.cursor() as cursor:
            for state, dist, city in locations_data:
                cursor.execute("""
                    SELECT id FROM locations WHERE state = %s AND district = %s AND city = %s
                """, (state, dist, city))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("""
                        INSERT INTO locations (state, district, city)
                        VALUES (%s, %s, %s)
                    """, (state, dist, city))
                    location_id_map[f"{state}-{dist}-{city}"] = cursor.lastrowid
                else:
                    location_id_map[f"{state}-{dist}-{city}"] = row['id']
        conn.commit()
        print(f"Seeded {len(location_id_map)} locations across major states.")

        # 6. Seed Tags
        tags_data = [
            ('Elections 2026', 'चुनाव 2026', 'elections-2026'),
            ('Artificial Intelligence', 'कृत्रिम बुद्धिमत्ता', 'artificial-intelligence'),
            ('Indian Economy', 'भारतीय अर्थव्यवस्था', 'indian-economy'),
            ('Cricket World Cup', 'क्रिकेट विश्व कप', 'cricket-world-cup'),
            ('ISRO Mission', 'इसरो मिशन', 'isro-mission'),
            ('Electric Vehicles', 'इलेक्ट्रिक वाहन', 'electric-vehicles'),
            ('Public Health', 'जन स्वास्थ्य', 'public-health'),
            ('Cinema', 'सिनेमा', 'cinema'),
            ('Smart Cities', 'स्मार्ट शहर', 'smart-cities'),
            ('Global Diplomacy', 'वैश्विक कूटनीति', 'global-diplomacy')
        ]

        tag_id_map = {}
        with conn.cursor() as cursor:
            for t_en, t_hi, t_slug in tags_data:
                cursor.execute("SELECT id FROM tags WHERE slug = %s", (t_slug,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("INSERT INTO tags (name_en, name_hi, slug) VALUES (%s, %s, %s)", (t_en, t_hi, t_slug))
                    tag_id_map[t_slug] = cursor.lastrowid
                else:
                    tag_id_map[t_slug] = row['id']
        conn.commit()
        print(f"Seeded {len(tag_id_map)} tags.")

        # 7. Seed Bilingual News Articles
        now = datetime.now()
        articles_data = [
            {
                'title_en': 'India Unveils Next-Gen High-Speed Green Rail Corridor Connecting 8 Mega Hubs',
                'title_hi': 'भारत ने 8 बड़े केंद्रों को जोड़ने वाले अगली पीढ़ी के हाई-स्पीड ग्रीन रेल कॉरिडोर का अनावरण किया',
                'slug': 'india-unveils-next-gen-high-speed-green-rail-corridor',
                'excerpt_en': 'The landmark infrastructure project aims to reduce transit times by 55% while running entirely on dedicated solar and wind renewable grids.',
                'excerpt_hi': 'इस ऐतिहासिक बुनियादी ढांचा परियोजना का लक्ष्य समर्पित सौर और पवन नवीकरणीय ग्रिड पर चलते हुए यात्रा समय को 55% तक कम करना है।',
                'content_en': '''<p>In a major leap forward for national infrastructure, the Ministry of Railways today announced the formal launch of the Next-Generation High-Speed Green Rail Corridor, connecting key metropolitan and industrial hubs across the nation.</p>
                <p>The state-of-the-art train network is designed to run at cruising speeds of 280 km/h, slashing travel times between commercial epicenters dramatically. More importantly, 100% of the traction energy will be sourced from dedicated solar parks and coastal wind turbine farms established under the National Clean Transit Directive.</p>
                <h3>Eco-Friendly Engineering</h3>
                <p>Engineers highlighted that the trains will utilize lightweight carbon-composite aerodynamic nose cones and regenerative electromagnetic braking systems, feeding up to 20% of generated deceleration energy back into the auxiliary power supply.</p>
                <blockquote>"This corridor isn't merely about speed; it redefines sustainable mass transit for the next half century," stated the Project Director during the inaugural briefing.</blockquote>
                <p>Initial commercial passenger and priority freight runs will commence early next quarter, with affordable tier ticketing ensuring mass accessibility.</p>''',
                'content_hi': '''<p>राष्ट्रीय बुनियादी ढांचे के क्षेत्र में एक बड़ी छलांग लगाते हुए, रेल मंत्रालय ने आज देश भर के प्रमुख महानगरीय और औद्योगिक केंद्रों को जोड़ने वाले अगली पीढ़ी के हाई-स्पीड ग्रीन रेल कॉरिडोर के औपचारिक शुभारंभ की घोषणा की।</p>
                <p>यह अत्याधुनिक ट्रेन नेटवर्क 280 किमी/घंटा की गति से चलने के लिए डिज़ाइन किया गया है, जिससे वाणिज्यिक केंद्रों के बीच यात्रा का समय नाटकीय रूप से कम हो जाएगा। इससे भी महत्वपूर्ण बात यह है कि राष्ट्रीय स्वच्छ पारगमन निर्देश के तहत स्थापित समर्पित सौर पार्कों और तटीय पवन टरबाइन फार्मों से 100% ऊर्जा प्राप्त की जाएगी।</p>
                <h3>पर्यावरण-अनुकूल इंजीनियरिंग</h3>
                <p>इंजीनियरों ने रेखांकित किया कि ट्रेनें हल्के कार्बन-कंपोजिट वायुगतिकीय नोज़ कोन और पुनर्योजी विद्युत-चुंबकीय ब्रेकिंग सिस्टम का उपयोग करेंगी, जो उत्पन्न ऊर्जा का 20% तक वापस ग्रिड में फीड करेगा।</p>
                <blockquote>"यह गलियारा केवल गति के बारे में नहीं है; यह अगली आधी सदी के लिए टिकाऊ जन पारगमन को पुनर्परिभाषित करता है," उद्घाटन के दौरान परियोजना निदेशक ने कहा।</blockquote>
                <p>प्रारंभिक वाणिज्यिक यात्री यात्राएं अगली तिमाही में शुरू होंगी, जिसमें किफायती टिकट दरें आम जनता की पहुंच सुनिश्चित करेंगी।</p>''',
                'category_slug': 'india',
                'location_key': 'Delhi-New Delhi-Connaught Place',
                'image_url': 'https://images.unsplash.com/photo-1474487548417-781cb71495f3?w=1200&auto=format&fit=crop',
                'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'is_breaking': 1,
                'is_featured': 1,
                'status': 'published',
                'views_count': 1420,
                'published_at': now - timedelta(minutes=15),
                'tags': ['indian-economy', 'smart-cities']
            },
            {
                'title_en': 'ISRO Prepares Breakthrough Lunar Polar Explorer for Deep Ice Cap Drilling',
                'title_hi': 'इसरो ने गहरे बर्फीले क्रेटर में ड्रिलिंग के लिए चंद्र ध्रुवीय अन्वेषक तैयार किया',
                'slug': 'isro-prepares-breakthrough-lunar-polar-explorer',
                'excerpt_en': 'The upcoming lunar mission will carry indigenous thermal drills capable of penetrating 3 meters into permanently shadowed crater basins to extract pristine water ice.',
                'excerpt_hi': 'आगामी चंद्र मिशन में स्वदेशी थर्मल ड्रिल ले जाई जाएगी जो प्राचीन जल बर्फ निकालने के लिए स्थायी रूप से छाया वाले क्रेटर में 3 मीटर तक प्रवेश करने में सक्षम होगी।',
                'content_en': '''<p>Building on the resounding global triumph of recent moon explorations, the Indian Space Research Organisation (ISRO) is entering the final testing phase of its Lunar Polar Ice Sampler module.</p>
                <p>The mission targets the treacherous, ultra-frigid craters situated at the Moon’s extreme South Pole, where sunlight never touches the crater floors and temperatures plunge below minus 230 degrees Celsius.</p>
                <h3>Advanced Sub-Surface Probes</h3>
                <p>Equipped with diamond-tipped cryogenic rotary drills, the robotic lander will extract continuous cylindrical cores of lunar permafrost. Onboard mass spectrometers and gas chromatographs will perform real-time chemical assays to quantify isotope ratios and volatile organic compounds.</p>
                <p>Scientists believe these measurements could unravel billion-year-old records of inner solar system cometary bombardments and confirm resources essential for future permanent crewed research habitats.</p>''',
                'content_hi': '''<p>हालिया चंद्र अभियानों की शानदार वैश्विक सफलता के बाद, भारतीय अंतरिक्ष अनुसंधान संगठन (इसरो) अपने चंद्र ध्रुवीय बर्फ नमूना मॉड्यूल के अंतिम परीक्षण चरण में प्रवेश कर रहा है।</p>
                <p>मिशन का लक्ष्य चंद्रमा के अत्यधिक दक्षिणी ध्रुव पर स्थित दुर्गम, अति-शीत क्रेटर हैं, जहां सूर्य का प्रकाश कभी क्रेटर के तल तक नहीं पहुंचता है और तापमान शून्य से 230 डिग्री सेल्सियस नीचे चला जाता है।</p>
                <h3>उन्नत सतह-अन्वेषण जांच</h3>
                <p>डायमंड-टिप्ड क्रायोजेनिक रोटरी ड्रिल से लैस, रोबोटिक लैंडर चंद्र पर्माफ्रॉस्ट के बेलनाकार कोर निकालेगा। बोर्ड पर मौजूद मास स्पेक्ट्रोमीटर आइसोटोप अनुपात और वाष्पशील कार्बनिक यौगिकों का विश्लेषण करेंगे।</p>
                <p>वैज्ञानिकों का मानना है कि ये माप सौर मंडल के अरबों साल पुराने रहस्यों को उजागर कर सकते हैं और भविष्य के स्थायी मानव अनुसंधान केंद्रों के लिए आवश्यक संसाधनों की पुष्टि कर सकते हैं।</p>''',
                'category_slug': 'technology',
                'location_key': 'Karnataka-Bengaluru Urban-Electronic City',
                'image_url': 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 1,
                'is_featured': 1,
                'status': 'published',
                'views_count': 2390,
                'published_at': now - timedelta(hours=1, minutes=10),
                'tags': ['isro-mission', 'artificial-intelligence']
            },
            {
                'title_en': 'Global Climate Summit Enacts Binding Cap on Industrial Methane Emissions',
                'title_hi': 'वैश्विक जलवायु शिखर सम्मेलन में औद्योगिक मीथेन उत्सर्जन पर बाध्यकारी सीमा लागू',
                'slug': 'global-climate-summit-enacts-binding-cap-methane',
                'excerpt_en': 'Over 140 nations ratify historic pact to cut super-potent greenhouse gas leakage across oil, gas, agriculture, and municipal landfills by 40%.',
                'excerpt_hi': '140 से अधिक देशों ने तेल, गैस, कृषि और लैंडफिल में अत्यधिक शक्तिशाली ग्रीनहाउस गैस रिसाव को 40% तक कम करने के ऐतिहासिक समझौते की पुष्टि की।',
                'content_en': '''<p>In a historic midnight consensus, delegates at the Global Climate Action Forum sealed a multilateral pact imposing strict, verifiable limits on point-source methane discharges.</p>
                <p>Methane, while shorter-lived in the atmosphere than carbon dioxide, possesses over 80 times the heat-trapping potency across a twenty-year timescale. The newly adopted framework mandates continuous satellite monitoring and automated thermal leakage audits across energy extraction pipelines.</p>
                <p>Financial assistance mechanisms totaling $45 billion were pledged to assist emerging economies in upgrading agricultural manure digestion plants and sealing abandoned fossil fuel wells.</p>''',
                'content_hi': '''<p>एक ऐतिहासिक मध्यरात्रि सहमति में, ग्लोबल क्लाइमेट एक्शन फोरम के प्रतिनिधियों ने मीथेन डिस्चार्ज पर सख्त और सत्यापन योग्य सीमा लगाने वाले एक बहुपक्षीय समझौते पर मुहर लगाई।</p>
                <p>मीथेन, हालांकि कार्बन डाइऑक्साइड की तुलना में वातावरण में कम समय तक रहती है, लेकिन बीस साल के समय में 80 गुना अधिक गर्मी सोखने की क्षमता रखती है। नए ढांचे में ऊर्जा पाइपलाइनों में उपग्रह निगरानी को अनिवार्य किया गया है।</p>
                <p>विकासशील अर्थव्यवस्थाओं को कृषि बायोगैस संयंत्रों के उन्नयन और पुराने कुओं को सील करने में सहायता के लिए $45 बिलियन की वित्तीय सहायता का संकल्प लिया गया।</p>''',
                'category_slug': 'world',
                'location_key': None,
                'image_url': 'https://images.unsplash.com/photo-1611273426858-450d8e3c9fce?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 1,
                'status': 'published',
                'views_count': 890,
                'published_at': now - timedelta(hours=2, minutes=45),
                'tags': ['global-diplomacy']
            },
            {
                'title_en': 'Sensex Surges Past Record 85,000 Mark Led by Tech, Banking and Renewable Energy Inflows',
                'title_hi': 'सेंसेक्स ने टेक, बैंकिंग और रिन्यूएबल शेयरों में भारी निवेश से 85,000 का ऐतिहासिक आंकड़ा पार किया',
                'slug': 'sensex-surges-past-record-85000-mark',
                'excerpt_en': 'Domestic institutional investors and foreign portfolios fuel explosive market rally as retail participation in mutual funds touches all-time peaks.',
                'excerpt_hi': 'घरेलू संस्थागत निवेशकों और विदेशी पोर्टफोलियो ने बाजार में जोरदार तेजी को बढ़ावा दिया, म्यूचुअल फंड में खुदरा भागीदारी सर्वकालिक उच्च स्तर पर पहुंची।',
                'content_en': '''<p>Bulls charged through Dalal Street today as benchmark indices shattered all previous records. The BSE Sensex closed above the psychological 85,000 milestone, buoyed by robust quarterly earnings across private banks, IT heavyweights, and green energy manufacturers.</p>
                <p>Market analysts attributed the sustained momentum to strong macroeconomic indicators, easing retail inflation, and unprecedented capital expenditure commitments announced for rural digital infrastructure.</p>
                <p>Trading desks reported heavy foreign portfolio buying, with net institutional purchases topping ₹6,800 crore in today's trading session alone.</p>''',
                'content_hi': '''<p>दलाल स्ट्रीट पर आज जबरदस्त उछाल देखने को मिला और बेंचमार्क सूचकांकों ने पिछले सभी रिकॉर्ड तोड़ दिए। बीएसई सेंसेक्स 85,000 के महत्वपूर्ण स्तर के पार बंद हुआ, जिसे निजी बैंकों, आईटी दिग्गजों और हरित ऊर्जा कंपनियों के मजबूत नतीजों से समर्थन मिला।</p>
                <p>बाजार विश्लेषकों ने इस तेजी का श्रेय मजबूत व्यापक आर्थिक संकेतकों, खुदरा मुद्रास्फीति में कमी और ग्रामीण डिजिटल बुनियादी ढांचे के लिए पूंजीगत व्यय को दिया।</p>
                <p>विदेशी पोर्टफोलियो निवेशकों ने आज के कारोबारी सत्र में ही ₹6,800 करोड़ से अधिक की शुद्ध संस्थागत खरीदारी दर्ज की।</p>''',
                'category_slug': 'business',
                'location_key': 'Maharashtra-Mumbai-South Mumbai',
                'image_url': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 1,
                'is_featured': 1,
                'status': 'published',
                'views_count': 3120,
                'published_at': now - timedelta(hours=3, minutes=20),
                'tags': ['indian-economy']
            },
            {
                'title_en': 'Parliament Passes Landmark Digital Healthcare and Telemedicine Equity Act',
                'title_hi': 'संसद ने ऐतिहासिक डिजिटल स्वास्थ्य सेवा और टेलीमेडिसिन समानता अधिनियम पारित किया',
                'slug': 'parliament-passes-digital-healthcare-act',
                'excerpt_en': 'The legislation guarantees high-speed video consultation and doorstep generic medicine delivery across 600,000 villages nationwide.',
                'excerpt_hi': 'यह कानून देश भर के 600,000 गांवों में हाई-स्पीड वीडियो परामर्श और घर-घर जेनेरिक दवाओं की डिलीवरी की गारंटी देता है।',
                'content_en': '''<p>Following a constructive bi-partisan debate, both houses of Parliament have passed the comprehensive Digital Healthcare & Telemedicine Equity Act with an overwhelming majority.</p>
                <p>The landmark bill establishes digital primary health centers in every Gram Panchayat, staffed by certified healthcare associates and integrated with AI diagnostic kiosks. Patients can connect directly with super-specialists at premier medical institutes without traveling hundreds of miles.</p>
                <p>The health minister emphasized that digital prescriptions will be seamlessly linked to PM Jan Aushadhi generic distribution channels, reducing out-of-pocket medical expenses for rural families by up to 70%.</p>''',
                'content_hi': '''<p>संसद के दोनों सदनों ने भारी बहुमत से व्यापक डिजिटल स्वास्थ्य सेवा और टेलीमेडिसिन समानता अधिनियम पारित कर दिया है।</p>
                <p>यह ऐतिहासिक विधेयक प्रत्येक ग्राम पंचायत में डिजिटल प्राथमिक स्वास्थ्य केंद्र स्थापित करता है, जहां प्रमाणित स्वास्थ्य कर्मी होंगे और जो एआई डायग्नोस्टिक कियोस्क से एकीकृत होंगे। मरीज सैकड़ों मील की यात्रा किए बिना प्रमुख चिकित्सा संस्थानों के विशेषज्ञों से सीधे जुड़ सकेंगे।</p>
                <p>स्वास्थ्य मंत्री ने जोर देकर कहा कि डिजिटल नुस्खे निर्बाध रूप से जन औषधि केंद्रों से जुड़े होंगे, जिससे ग्रामीण परिवारों के इलाज का खर्च 70% तक कम हो जाएगा।</p>''',
                'category_slug': 'politics',
                'location_key': 'Delhi-New Delhi-Connaught Place',
                'image_url': 'https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 0,
                'status': 'published',
                'views_count': 1180,
                'published_at': now - timedelta(hours=4, minutes=10),
                'tags': ['elections-2026', 'public-health']
            },
            {
                'title_en': 'Lucknow Metro Completes Underground Extension Connecting Historic Old City to Airport',
                'title_hi': 'लखनऊ मेट्रो ने पुराने शहर को हवाई अड्डे से जोड़ने वाले भूमिगत विस्तार को पूरा किया',
                'slug': 'lucknow-metro-completes-underground-extension',
                'excerpt_en': 'Commuters in Lucknow can now travel from Chowk to Chaudhary Charan Singh International Airport in under 26 minutes with contactless ticketing.',
                'excerpt_hi': 'लखनऊ के यात्री अब चौक से चौधरी चरण सिंह अंतर्राष्ट्रीय हवाई अड्डे तक बिना किसी संपर्क के टिकट लेकर 26 मिनट से भी कम समय में यात्रा कर सकते हैं।',
                'content_en': '''<p>The capital of Uttar Pradesh marked a major transit milestone today with the trial completion of the 11.2 km underground metro segment threading through the historic corridors of Old Lucknow.</p>
                <p>Designed with architectural motifs honoring Awadhi heritage, the newly constructed subterranean stations feature state-of-the-art tunnel ventilation and automated platform screen doors.</p>
                <p>Urban planners project that the corridor will eliminate over 45,000 vehicular trips daily along congested arterial roads like MG Marg and Ring Road, cutting urban air particulate pollution significantly.</p>''',
                'content_hi': '''<p>उत्तर प्रदेश की राजधानी ने आज पुराने लखनऊ के ऐतिहासिक गलियारों से गुजरने वाले 11.2 किलोमीटर के भूमिगत मेट्रो खंड के परीक्षण के साथ एक बड़ा मील का पत्थर हासिल किया।</p>
                <p>अवधी विरासत को सम्मान देने वाले स्थापत्य रूपांकनों के साथ डिज़ाइन किए गए इन नवनिर्मित स्टेशनों में अत्याधुनिक सुरंग वेंटिलेशन और स्वचालित स्क्रीन दरवाजे शामिल हैं।</p>
                <p>नियोजकों का अनुमान है कि यह गलियारा एमजी मार्ग और रिंग रोड जैसी भीड़भाड़ वाली सड़कों पर प्रतिदिन 45,000 से अधिक वाहनों की यात्रा को कम करेगा, जिससे शहरी प्रदूषण में भारी कमी आएगी।</p>''',
                'category_slug': 'local-news',
                'location_key': 'Uttar Pradesh-Lucknow-Lucknow Central',
                'image_url': 'https://images.unsplash.com/photo-1517649763962-0c623266ddc0?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 1,
                'status': 'published',
                'views_count': 940,
                'published_at': now - timedelta(hours=5),
                'tags': ['smart-cities']
            },
            {
                'title_en': 'Mumbai Coastal Road Phase 2 Opens to Traffic: Marine Drive to Kandivali in 40 Minutes',
                'title_hi': 'मुंबई कोस्टल रोड फेज़ 2 यातायात के लिए खुला: मरीन ड्राइव से कांदिवली 40 मिनट में',
                'slug': 'mumbai-coastal-road-phase-2-opens',
                'excerpt_en': 'The undersea tunnel and sea link bridges revolutionize Western Mumbai commutes with scenic seaside promenades and dedicated EV charging corridors.',
                'excerpt_hi': 'समुद्र के नीचे बनी सुरंग और सी-लिंक पुलों ने पश्चिमी मुंबई के आवागमन में क्रांति ला दी है, जिसमें सुंदर सैरगाह और ईवी चार्जिंग कॉरिडोर शामिल हैं।',
                'content_en': '''<p>Western suburban commuters in Mumbai experienced unprecedented relief this morning as the second phase of the ambitious Coastal Road project was formally commissioned for regular vehicular traffic.</p>
                <p>The engineering marvel features twin twin-lane undersea tunnels bored beneath the Arabian seabed, coupled with elevated viaducts offering panoramic vistas of the Arabian Sea shoreline.</p>
                <p>Traffic monitoring centers recorded smooth average vehicle flows of 75 km/h, slashing what used to be an exhausting two-hour peak gridlock into a brisk 38-minute drive.</p>''',
                'content_hi': '''<p>मुंबई में पश्चिमी उपनगरीय यात्रियों को आज सुबह अभूतपूर्व राहत मिली जब महत्वाकांक्षी तटीय सड़क परियोजना के दूसरे चरण को नियमित यातायात के लिए चालू किया गया।</p>
                <p>इस इंजीनियरिंग चमत्कार में अरब सागर के नीचे खोदी गई दोहरी लेन वाली समुद्र के नीचे की सुरंगें हैं, साथ ही समुद्र तट के मनोरम दृश्य प्रस्तुत करने वाले एलिवेटेड पुल शामिल हैं।</p>
                <p>यातायात केंद्रों ने 75 किमी/घंटा का सुचारू प्रवाह दर्ज किया, जिससे दो घंटे का भारी जाम केवल 38 मिनट की सुखद यात्रा में बदल गया।</p>''',
                'category_slug': 'local-news',
                'location_key': 'Maharashtra-Mumbai-Bandra Suburban',
                'image_url': 'https://images.unsplash.com/photo-1570168007204-dfb528c6958f?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 0,
                'status': 'published',
                'views_count': 1670,
                'published_at': now - timedelta(hours=6, minutes=30),
                'tags': ['smart-cities']
            },
            {
                'title_en': 'ICC Champions Trophy: Team India Clinches Dramatic Last-Over Victory with Brilliant Bowling',
                'title_hi': 'आईसीसी चैंपियंस ट्रॉफी: शानदार गेंदबाजी से टीम इंडिया ने आखिरी ओवर में रोमांचक जीत दर्ज की',
                'slug': 'icc-champions-trophy-india-dramatic-victory',
                'excerpt_en': 'Defending 12 runs in the tense final over, Jasprit Bumrah produces three consecutive yorkers to send the stadium into wild celebrations.',
                'excerpt_hi': 'तनावपूर्ण अंतिम ओवर में 12 रनों का बचाव करते हुए, जसप्रीत बुमराह ने लगातार तीन सटीक यॉर्कर फेंककर पूरे स्टेडियम को जश्न में डुबो दिया।',
                'content_en': '''<p>In one of the most heart-stopping climaxes in recent cricket history, Team India edged out rivals in a nail-biting encounter at the packed stadium tonight.</p>
                <p>Having posted a competitive 287 on a wearing pitch thanks to a sublime century by the vice-captain, the match seemed to be slipping away in the death overs as the opposition lower order launched a spirited counter-attack.</p>
                <p>However, bowling the decisive 50th over, spearhead Jasprit Bumrah delivered a masterclass in reverse swing and pinpoint yorkers, conceding just four runs and claiming two wickets to seal an unforgettable triumph.</p>''',
                'content_hi': '''<p>क्रिकेट इतिहास के सबसे रोमांचक मुकाबलों में से एक में, टीम इंडिया ने आज रात खचाखच भरे स्टेडियम में कड़े मुकाबले में जीत हासिल की।</p>
                <p>उप-कप्तान के शानदार शतक की बदौलत धीमी पिच पर 287 रन बनाने के बाद, मैच अंतिम ओवरों में हाथ से फिसलता दिख रहा था जब विपक्षी बल्लेबाजों ने तेज प्रहार शुरू कर दिए।</p>
                <p>हालाँकि, निर्णायक 50वां ओवर फेंकते हुए, जसप्रीत बुमराह ने रिवर्स स्विंग और यॉर्कर का अद्भुत प्रदर्शन किया, केवल चार रन दिए और दो विकेट लेकर जीत पक्की की।</p>''',
                'category_slug': 'sports',
                'location_key': None,
                'image_url': 'https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 1,
                'is_featured': 1,
                'status': 'published',
                'views_count': 4580,
                'published_at': now - timedelta(hours=7),
                'tags': ['cricket-world-cup']
            },
            {
                'title_en': 'AI Generative Models Achieve Real-Time Multilingual Simultaneous Voice Translation',
                'title_hi': 'एआई जेनरेटिव मॉडल ने रीयल-टाइम बहुभाषी वॉयस ट्रांसलेशन में हासिल की बड़ी सफलता',
                'slug': 'ai-models-achieve-real-time-multilingual-translation',
                'excerpt_en': 'New ultra-low latency transformer architecture enables conversations across 35 languages while preserving natural vocal pitch, cadence, and emotion.',
                'excerpt_hi': 'नए अल्ट्रा-लो लेटेंसी आर्किटेक्चर ने आवाज की पिच, टोन और भावना को बनाए रखते हुए 35 भाषाओं में बातचीत को संभव बना दिया है।',
                'content_en': '''<p>Artificial intelligence researchers have published groundbreaking results demonstrating instantaneous, fluid speech-to-speech translation with sub-100-millisecond latency.</p>
                <p>Unlike previous multi-stage cascades (speech-to-text, translation, text-to-speech), the new end-to-end neural system directly transforms audio acoustic waves from the source language into target language phonemes, preserving the speaker's emotional nuance and natural vocal identity.</p>
                <p>Educational and medical sectors across rural multilingual regions are anticipated to be the immediate beneficiaries of this democratizing innovation.</p>''',
                'content_hi': '''<p>आर्टिफिशियल इंटेलिजेंस शोधकर्ताओं ने 100-मिलीसेकंड से कम समय में तात्कालिक, धाराप्रवाह भाषण-से-भाषण अनुवाद प्रदर्शित करने वाले अभूतपूर्व परिणाम प्रकाशित किए हैं।</p>
                <p>पुरानी प्रणालियों के विपरीत, नया न्यूरल सिस्टम स्रोत भाषा से सीधे लक्षित भाषा की ध्वनि तरंगों में ऑडियो को बदलता है, जिससे वक्ता की भावना और प्राकृतिक आवाज सुरक्षित रहती है।</p>
                <p>ग्रामीण बहुभाषी क्षेत्रों में शैक्षिक और चिकित्सा क्षेत्रों को इस नवाचार का तत्काल लाभार्थी माना जा रहा है।</p>''',
                'category_slug': 'technology',
                'location_key': 'Karnataka-Bengaluru Urban-Indiranagar',
                'image_url': 'https://images.unsplash.com/photo-1677442136019-21780ecad995?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 0,
                'status': 'published',
                'views_count': 1890,
                'published_at': now - timedelta(hours=8, minutes=15),
                'tags': ['artificial-intelligence']
            },
            {
                'title_en': 'National Film Awards Announced: Pan-India Epics and Indie Social Dramas Sweep Honors',
                'title_hi': 'राष्ट्रीय फिल्म पुरस्कारों की घोषणा: पैन-इंडिया महाकाव्यों और सामाजिक नाटकों का दबदबा',
                'slug': 'national-film-awards-announced-honors',
                'excerpt_en': 'Jury celebrates cinematic brilliance across Hindi, Tamil, Malayalam, and Bengali languages, recognizing realistic grassroots storytelling.',
                'excerpt_hi': 'जूरी ने जमीनी स्तर की यथार्थवादी कहानियों को पहचानते हुए हिंदी, तमिल, मलयालम और बंगाली भाषाओं में सिनेमाई उत्कृष्टता का सम्मान किया।',
                'content_en': '''<p>The prestigious National Film Awards were officially unveiled today at an illustrious ceremony in New Delhi, celebrating diverse voices and groundbreaking cinematic vision across India's vibrant regional film industries.</p>
                <p>The coveted Best Feature Film trophy was awarded to a critically lauded indie drama chronicling the resilient spirit of rural women farmers, while Best Actor honors were jointly conferred upon two powerhouse performances in historical and modern psychological thrillers.</p>
                <p>Critics applauded the selection committee for spotlighting emerging storytellers alongside big-budget technical masterpieces.</p>''',
                'content_hi': '''<p>प्रतिष्ठित राष्ट्रीय फिल्म पुरस्कारों की आधिकारिक घोषणा आज नई दिल्ली में एक भव्य समारोह में की गई, जिसमें भारत के जीवंत क्षेत्रीय सिनेमा की विविधता का सम्मान किया गया।</p>
                <p>सर्वश्रेष्ठ फीचर फिल्म की प्रतिष्ठित ट्रॉफी ग्रामीण महिला किसानों के संघर्ष पर आधारित एक सामाजिक नाटक को दी गई, जबकि सर्वश्रेष्ठ अभिनेता का पुरस्कार संयुक्त रूप से ऐतिहासिक और मनोवैज्ञानिक थ्रिलर के कलाकारों को मिला।</p>
                <p>आलोचकों ने बड़े बजट की फिल्मों के साथ-साथ उभरते हुए स्वतंत्र निर्देशकों को प्रोत्साहित करने के लिए जूरी की सराहना की।</p>''',
                'category_slug': 'entertainment',
                'location_key': 'Delhi-New Delhi-Connaught Place',
                'image_url': 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 0,
                'status': 'published',
                'views_count': 2240,
                'published_at': now - timedelta(hours=9, minutes=40),
                'tags': ['cinema']
            },
            {
                'title_en': 'Medical Breakthrough: Indigenous CAR-T Cell Therapy Approved for Low-Cost Cancer Treatment',
                'title_hi': 'चिकित्सा जगत में क्रांति: कम लागत वाले कैंसर उपचार के लिए स्वदेशी CAR-T सेल थेरेपी को मंजूरी',
                'slug': 'indigenous-car-t-cell-therapy-approved',
                'excerpt_en': 'Revolutionary targeted immunotherapy developed by top bio-engineers reduces advanced leukemia treatment expenses by up to 90%.',
                'excerpt_hi': 'शीर्ष बायो-इंजीनियरों द्वारा विकसित क्रांतिकारी इम्यूनोथेरेपी ने ल्यूकेमिया के इलाज के खर्च को 90% तक कम कर दिया है।',
                'content_en': '''<p>In a historic victory for affordable oncology, the Central Drugs Standard Control Organisation (CDSCO) has granted full regulatory approval for commercial manufacture of the nation's first indigenous CAR-T cell immunotherapy.</p>
                <p>The therapy involves genetically reprogramming a patient's own T-cells in specialized bioreactors to specifically target and eradicate malignant cancer cells without damaging healthy tissues.</p>
                <p>Previously costing over ₹3 crore abroad, the homegrown solution brings this life-saving protocol down to under ₹25 lakh, with public hospital subsidies bringing it within reach of underprivileged patients.</p>''',
                'content_hi': '''<p>सस्ती कैंसर चिकित्सा के लिए एक ऐतिहासिक सफलता में, केंद्रीय औषधि मानक नियंत्रण संगठन (सीडीएससीओ) ने देश की पहली स्वदेशी CAR-T सेल इम्यूनोथेरेपी को पूर्ण मंजूरी दे दी है।</p>
                <p>इस थेरेपी में मरीज की अपनी टी-कोशिकाओं को आनुवंशिक रूप से रीप्रोग्राम किया जाता है ताकि वे स्वस्थ ऊतकों को नुकसान पहुंचाए बिना कैंसर कोशिकाओं को नष्ट कर सकें।</p>
                <p>विदेशों में ₹3 करोड़ से अधिक खर्च वाली यह तकनीक अब ₹25 लाख से कम में उपलब्ध होगी, और सरकारी अस्पतालों में सब्सिडी के साथ गरीबों के लिए भी सुलभ होगी।</p>''',
                'category_slug': 'health',
                'location_key': 'Maharashtra-Mumbai-South Mumbai',
                'image_url': 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 1,
                'is_featured': 0,
                'status': 'published',
                'views_count': 1730,
                'published_at': now - timedelta(hours=11, minutes=10),
                'tags': ['public-health']
            },
            {
                'title_en': 'Patna AIIMS Inaugurates Advanced Neonatal Critical Care Center with 200 Beds',
                'title_hi': 'एम्स पटना ने 200 बिस्तरों वाले उन्नत नवजात क्रिटिकल केयर सेंटर का उद्घाटन किया',
                'slug': 'patna-aiims-inaugurates-advanced-neonatal-center',
                'excerpt_en': 'Equipped with robotic incubators and ECMO units, the super-specialty wing will provide free tertiary treatment to high-risk infants from Bihar and neighboring states.',
                'excerpt_hi': 'रोबोटिक इनक्यूबेटर और ईसीएमओ इकाइयों से लैस, यह सुपर-स्पेशियलिटी विंग बिहार और पड़ोसी राज्यों के नवजात शिशुओं को मुफ्त तृतीयक उपचार प्रदान करेगा।',
                'content_en': '''<p>A massive fillip was delivered to pediatric healthcare in Eastern India today as AIIMS Patna commissioned its state-of-the-art Neonatal and Pediatric Intensive Care Complex.</p>
                <p>The facility features 200 micro-filtered negative-pressure beds, round-the-clock point-of-care ultrasound, and dedicated air ambulance transport links for remote rural districts.</p>
                <p>State authorities reiterated that all emergency pediatric services will be covered completely under cashless universal health schemes.</p>''',
                'content_hi': '''<p>एम्स पटना ने आज अपने अत्याधुनिक नवजात और बाल चिकित्सा गहन देखभाल परिसर की शुरुआत करके पूर्वी भारत में बाल स्वास्थ्य सेवा को मजबूत किया।</p>
                <p>इस केंद्र में 200 माइक्रो-फ़िल्टर्ड नेगेटिव-प्रेशर बेड, 24 घंटे अल्ट्रासाउंड और दूरदराज के जिलों के लिए एयर एम्बुलेंस की सुविधा है।</p>
                <p>राज्य के अधिकारियों ने दोहराया कि सभी आपातकालीन बाल चिकित्सा सेवाएं कैशलेस स्वास्थ्य योजनाओं के तहत पूरी तरह से मुफ्त होंगी।</p>''',
                'category_slug': 'local-news',
                'location_key': 'Bihar-Patna-Patna Central',
                'image_url': 'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 0,
                'status': 'published',
                'views_count': 810,
                'published_at': now - timedelta(hours=13, minutes=20),
                'tags': ['public-health']
            },
            {
                'title_en': 'Varanasi Launches Zero-Emission Solar Ferry Fleet on Holy River Ganga',
                'title_hi': 'वाराणसी में पवित्र गंगा नदी पर शून्य-उत्सर्जन सौर नौका बेड़े का संचालन शुरू',
                'slug': 'varanasi-launches-solar-ferry-fleet-ganga',
                'excerpt_en': 'Silent, solar-powered catamarans now carry pilgrims and tourists along the 84 ghats from Assi to Rajghat without noise or water pollution.',
                'excerpt_hi': 'मौन, सौर-संचालित कैटामारन अब बिना किसी शोर या जल प्रदूषण के अस्सी से राजघाट तक 84 घाटों पर श्रद्धालुओं और पर्यटकों को ले जा रहे हैं।',
                'content_en': '''<p>In a tranquil blend of timeless spirituality and cutting-edge renewable technology, Varanasi today inaugurated a brand-new fleet of twenty solar-electric passenger catamarans across the Ganga.</p>
                <p>Each vessel is capped with high-efficiency flexible monocrystalline solar arrays feeding lithium iron phosphate batteries, guaranteeing silent, zero-emission travel along the world-famous ghats.</p>
                <p>Pilgrims expressed delight at experiencing the evening Ganga Aarti without the acoustic roar and diesel exhaust fumes of obsolete motor boats.</p>''',
                'content_hi': '''<p>शाश्वत आध्यात्मिकता और नवीकरणीय तकनीक के संगम में, वाराणसी में आज गंगा पर बीस सोलर-इलेक्ट्रिक यात्री नावों के एक नए बेड़े का उद्घाटन किया गया।</p>
                <p>प्रत्येक नाव मोनोक्रिस्टलाइन सौर पैनलों से सुसज्जित है जो लिथियम बैटरी को चार्ज करती हैं, जिससे विश्व प्रसिद्ध घाटों के साथ मौन और प्रदूषण मुक्त यात्रा सुनिश्चित होती है।</p>
                <p>श्रद्धालुओं ने पुराने डीजल इंजनों के धुएं और तेज आवाज के बिना शाम की दिव्य गंगा आरती का अनुभव करने पर खुशी व्यक्त की।</p>''',
                'category_slug': 'local-news',
                'location_key': 'Uttar Pradesh-Varanasi-Kashi City',
                'image_url': 'https://images.unsplash.com/photo-1561361513-2d000a50f0dc?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 1,
                'status': 'published',
                'views_count': 1320,
                'published_at': now - timedelta(hours=15),
                'tags': ['smart-cities']
            },
            {
                'title_en': 'Draft Policy on Urban Aerial Drone Corridors Under Internal Ministry Review',
                'title_hi': 'शहरी हवाई ड्रोन गलियारों पर मसौदा नीति आंतरिक मंत्रालय की समीक्षा के अधीन',
                'slug': 'draft-policy-urban-aerial-drone-corridors',
                'excerpt_en': 'Proposed safety framework for commercial drone logistics is currently undergoing technical validation before public comment period.',
                'excerpt_hi': 'वाणिज्यिक ड्रोन रसद के लिए प्रस्तावित सुरक्षा ढांचा वर्तमान में सार्वजनिक समीक्षा से पहले तकनीकी सत्यापन के दौर से गुजर रहा है।',
                'content_en': '<p>This is an internal working draft outlining altitude ceilings and automated geofencing protocols for delivery unmanned aerial vehicles. It will be scheduled for formal release after stakeholder consensus.</p>',
                'content_hi': '<p>यह डिलीवरी ड्रोन के लिए ऊंचाई सीमा और स्वचालित जियोफेंसिंग प्रोटोकॉल की रूपरेखा तैयार करने वाला एक आंतरिक मसौदा है। इसे हितधारकों की सहमति के बाद औपचारिक रूप से जारी किया जाएगा।</p>',
                'category_slug': 'technology',
                'location_key': None,
                'image_url': 'https://images.unsplash.com/photo-1527977966376-1c8408f9f108?w=1200&auto=format&fit=crop',
                'video_url': None,
                'is_breaking': 0,
                'is_featured': 0,
                'status': 'draft',  # DRAFT! Should never show on public news site!
                'views_count': 0,
                'published_at': None,
                'tags': ['artificial-intelligence']
            }
        ]

        inserted_articles = 0
        with conn.cursor() as cursor:
            for art in articles_data:
                cursor.execute("SELECT id FROM news WHERE slug = %s", (art['slug'],))
                exists = cursor.fetchone()
                if not exists:
                    cat_id = cat_id_map.get(art['category_slug'])
                    loc_id = location_id_map.get(art['location_key']) if art['location_key'] else None
                    cursor.execute("""
                        INSERT INTO news (
                            title_en, title_hi, slug, excerpt_en, excerpt_hi,
                            content_en, content_hi, category_id, location_id,
                            image_url, video_url, is_breaking, is_featured,
                            status, views_count, published_at, created_by
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                    """, (
                        art['title_en'], art['title_hi'], art['slug'], art['excerpt_en'], art['excerpt_hi'],
                        art['content_en'], art['content_hi'], cat_id, loc_id,
                        art['image_url'], art['video_url'], art['is_breaking'], art['is_featured'],
                        art['status'], art['views_count'], art['published_at'], admin_id
                    ))
                    news_id = cursor.lastrowid
                    inserted_articles += 1

                    # Attach tags
                    for t_slug in art.get('tags', []):
                        tag_id = tag_id_map.get(t_slug)
                        if tag_id:
                            cursor.execute("INSERT IGNORE INTO news_tags (news_id, tag_id) VALUES (%s, %s)", (news_id, tag_id))

                    # Seed sample comments & likes on published articles
                    if art['status'] == 'published' and user_id:
                        cursor.execute("""
                            INSERT IGNORE INTO likes (news_id, user_id) VALUES (%s, %s)
                        """, (news_id, user_id))
                        
                        if inserted_articles % 2 == 0:
                            cursor.execute("""
                                INSERT IGNORE INTO bookmarks (news_id, user_id) VALUES (%s, %s)
                            """, (news_id, user_id))
                            
                            cursor.execute("""
                                INSERT INTO comments (news_id, user_id, comment_text, status)
                                VALUES (%s, %s, %s, 'approved')
                            """, (news_id, user_id, "Very thorough coverage! Great to see in-depth journalism on this critical development."))
        
        conn.commit()
        print(f"Seeded {inserted_articles} articles (including breaking, featured, local, and draft samples).")
        print("\nAll database setup completed successfully!")

    finally:
        conn.close()

if __name__ == '__main__':
    init_database()
