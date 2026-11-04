"""위키미디어 공용 사진 받기 + 출처 기록.

./.venv/bin/python fetch_photos.py            # PHOTOS 목록을 받아 assets/photos/ 에 저장, credits.json 갱신
라이선스가 허용 목록에 없으면 받지 않는다.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "assets" / "photos"
UA = {"User-Agent": "MonsterDogamResearch/0.1 (local research; python-urllib)"}
# "No restrictions"(DPLA·도서관의 {{NKC}} = '알려진 제한 없음')는 PD 근거가 아니라서 넣지 않는다.
OK = ("Public domain", "CC0", "CC BY ", "CC BY-SA ", "PD")

# 키: 위키미디어 파일 이름
PHOTOS = {
    "scarberry_sketch": "Mothman Roger Scarberry Sketch.jpg",
    "statue": "Mothman Statue.jpg",
    "statue2": "Mothman Statue 23 May 2009.jpg",
    "window_sighting": "Mothman.jpeg",
    "bridge_collapsed": "Silver Bridge which collapsed into Ohio River - DPLA - 5c0036e5b9e2b4bd3af8bdee5b8a58b0 (page 1).jpg",
    "bridge_collapsed_b": "Silver Bridge which collapsed into Ohio River - DPLA - 5c0036e5b9e2b4bd3af8bdee5b8a58b0 (page 2).jpg",
    "bridge_old": "Silver Bridge - DPLA - 9fc0bcf07698072f128124fc79edd1c7 (page 1).jpg",
    "bridge_old_b": "Silver Bridge - DPLA - 9fc0bcf07698072f128124fc79edd1c7 (page 2).jpg",
    "bridge_sign": "Silver Bridge Collapse Signage (5070040586).jpg",
    "wvow_lab": "Laboratory and Supervisors Office Acid Area West Virginia Ordnance Works.jpg",
    "wvow_aerial": "Aerial of Staffhouse Row and Dormatories at West Virginia Ordnance Works.jpg",
    "igloo": "Ammunition Igloo (11018683665).jpg",
    "car_night": "Inside a car at night-time in Williamsburg (Unsplash).jpg",
    "road_night": "Country Road at Night.jpg",
    "forest_moon": "Forest Moonlight (193503497).jpeg",
    "red_owl": "Red Eyed Owl.jpg",
    "barred_owl": "Barred Owl (16946154418).jpg",
    "museum": "Mothman Museum.jpg",
    # --- #002 네스호의 괴물
    "surgeon": "Loch Ness Monster Surgeon's photograph.jpg",
    "grant_1934": "Arthur Grant Loch Ness monster.png",
    "mackay_plaque": "Plaque-20260829 111823, Drumnadrochit, The Highlands, Scotland.jpg",
    "urquhart_cc0": "Urquhart Castle on Loch Ness.jpg",
    "storm_loch": "Storm clouds over Loch Ness - geograph.org.uk - 6660374.jpg",
    "misty_b852": "A misty Loch Ness by the B852 - geograph.org.uk - 6687154.jpg",
    "winter_loch": "Winter sunshine on Loch Ness - geograph.org.uk - 1734109.jpg",
    "eel_head": "Anguilla anguilla head.jpg",
    "eel_tank": "Hal - Anguilla anguilla - 1.jpg",
    "sonar_elac": "Echolot hg.jpg",
    "plesio": "Cryptoclidus.JPG",
    "columba_hole": "Saint Columba converting the Picts.jpg",
    # --- #003 플라이트 19
    "tbf_formation": "TBF's flying in formation. Fort Lauderdale, Fla - NARA - 520767.jpg",
    "taylor": "Charles C. Taylor.jpg",
    "f19_navmap": "Bermuda Triangle, Flight 19 Map of Navigation Problem Nr. 1, 1945.jpg",
    "tbm_vt88": "TBM Avengers of VT-88 in flight in August 1945.jpg",
    "tbm_night": "TBM VT-90 CV-6 Jan1945.jpg",
    "pbm5": "Martin PBM-5 Mariner in flight c1945.jpeg",
    "radio_room": "Merchant Marine Radio Operator and Radio Room SS Rockland Park - 1945.jpg",
    "noaa_storm": "Wea00820 - Flickr - NOAA Photo Library.jpg",
    "langley_seas": "USS Langley (CVL-27) in heavy seas 1944.jpeg",
    "flt19_map": "Flt19.png",
    # --- #004 디아틀로프 고개
    "dy_tent": "Dyatlov Pass incident 02.jpg",
    "dy_memorial": "Памятник дятловцам на Михайловском кладбище.jpg",
    "dy_portraits": "Фото членов тургруппы Игоря Дятлова.jpg",
    "dy_closed": "Dyatlov.Volume 1.Page 384.jpg",
    "dy_radiation": "Dyatlov.Volume 1.Page 370.jpg",
    "dy_case_open": "Dyatlov.Volume 1.Page 1.jpg",
    "ural_forest": "Зимний уральский лес.jpg",
    "otorten": "Гора Отортен. Североуральский минимализм.jpg",
    "dy_1958": "Поход на Приполярный Урал (январь 1958 года) - 51906749096.jpg",
    "dy_tent1958": "Поход на Приполярный Урал (январь 1958 года) - 51906843848.jpg",
    "dy_3d": "3d model of dyatlov pass 1.png",
    "night_forest": "Twilight, stars, snowy forest - panoramio.jpg",
    # --- 모스맨 롱폼
    "clendenin": "Clendenin West Virginia.jpg",
    "confluence": "Kanawha Ohio confluence.jpg",
    "nara_1973": "VIEW FROM TU-ENDIE-WEI PARK, AT PT. PLEASANT, ON THE POINT FORMED BY THE JUNCTION OF THE OHIO AND KANAWHA RIVERS. THE... - NARA - 551166.jpg",
    "bridges_aerial": "Silver and Point Pleasant Bridges aerial 2019.jpg",
    "hercilio": "Hercílio Luz Bridge 003.jpg",
    "hercilio2": "Ponte Hercílio Luz (3420623363).jpg",
    "ptp_downtown": "Downtown Point Pleasant, a city on the Ohio River in West Virginia LCCN2015631945.tif",
    "festival": "2011 Mothman Festival.jpg",
    "museum2025": "Mothman Museum 2025.jpg",
    "statue2025": "Mothman Statue 2025.jpg",
    "sandhill": "Sandhill portrait - Flickr - Andrea Westmoreland.jpg",
    "owl_night": "Owl at Night.jpg",
    "snowy_owl": "Snowy Owl (Bubo scandiacus) (15382921344).jpg",
    "chicago_night": "Chicago Lakefront Night Skyline.jpg",
    "chicago_river": "Chicago Skyline on the Chicago River at night.jpg",
    "barker_ad": "They Knew Too Much About Flying Saucers ad.png",
    "rt62": "2017-07-24 14 45 21 View north along West Virginia State Route 62 (Viand Street) between 6th Street and 8th Street in Point Pleasant, Mason County, West Virginia.jpg",
    # --- #006 로지 (버려진 수족관의 백상아리)
    "rosie": "Tom Kapitany and Sharon Williamson with Rosie the Shark.jpg",
    "gw_dark": "7989 S Africa white shark JF.jpg",
    "gw_hunt": "8185 white shark hunts JF.jpg",
    "gw_agulhas": "Cape Agulhas white shark JF2.jpg",
    "gw_gansbaai": "Carcharodon carcharias, Gansbaai (South Africa).jpg",
    "gw_attack": "Attacking great white shark.jpg",
    "gw_beach": "Beached great white shark.jpg",
    "gw_tank": "Great white aqurium.jpg",
    "aband_in": "Interior of abandoned building in Hermanninranta, Sörnäinen, Helsinki, 2021 July.jpg",
    "aband_in2": "Interior of abandoned building in Hermanninranta, Sörnäinen, Helsinki, 2021 July - 3.jpg",
    "aband_flood": "Flooded interior of abandoned factory.jpg",
    "aband_hosp": "Exploring an abandoned hospital (16439249053).jpg",
    "glass_broken": "Broken window glass in Esbjerg, 3.jpg",
    "glass_broken2": "Broken window glass in Esbjerg, 5.jpg",
    "jars": "Wet-preserved embryological specimens.jpg",
    "seine": "Purse seine in Austevoll.jpg",
    "boat_pl": "Fishing Boats - Port Lincoln Marina - South Australia.jpg",
    "crane_truck": "Dv12 lifted on a truck.jpg",
    "bass_coast": "Jam Jerrup VIC 3984, Australia - panoramio.jpg",
    # --- #007 빅풋
    "bf_casts": "Grover Krantz shows plaster casts of Bigfoot footprints.jpg",
    "bf_deerhair": "CSIRO ScienceImage 7131 Deer hair fibre.jpg",
    "bf_bear_stand": "Black bear near Phantom Lake (33074dca-2308-4d2f-b209-3c91bf3a03cb).jpg",
    "bf_bear_dump": "Black bear and dumpster (15ed1c45-1dd8-b71b-0bf0-efab2f1b518a).jpg",
    "bf_grizzly": "Standing Grizzly Bear Cub (Ursus arctos horribilis) (51556280998).jpg",
    "bf_dzunukwa": "Wild Woman of the Woods - Flickr - brewbooks.jpg",
    "bf_mask": "Kwakiutl Dsonoqua mask - Cleveland Museum of Natural History (34414484230).jpg",
    "bf_apecanyon": "Ape Canyon in WA.jpg",
    "bf_sthelens": "MSH80 eruption mount st helens 05-18-80-dramatic-edit.jpg",
    "bf_tetejaune": "Tete jaune Cache aerial view.JPG",
    "bf_orleans": "Orleans Bridge California, Humboldt County (29012253511).jpg",
    "bf_sixrivers": "Aikens Creek Recreation Area - Six Rivers National Forest, California (39812044524).jpg",
    "bf_redwood": "Redwood National Park REDW9360.jpg",
    "bf_fog": "Foggy old growth forest - Flickr - brandonkochpc.jpg",
    "bf_moss": "Mossy Forest (Olympic National Park).jpg",
    "bf_logging57": "484255 Mulching Machine on Logging Road, Siuslaw NF, OR 1957 (22107101243).jpg",
    "bf_logging37": "1937. Coates logging road. Tillamook Burn, OR. (34829797512).jpg",
    "bf_giganto_jaw": "Gigantopithecus blacki mandible 010112.jpg",
    "bf_giganto": "Gigantopithecus blacki restoration.jpg",
    "bf_model": "Murphy the Bigfoot.jpg",
    "bf_statue": "Boring Bigfoot.jpg",
    "bf_museum": "Bigfoot Museum Willow Creek.jpg",
    "bf_museum2": "Exterior to the bigfoot discovery museum 2023.jpg",
    "bf_fbi": "February 2019 - FBI Rubber Stamps (32289018487).jpg",
    # --- #008 제보당의 야수
    "gv_record": "AD07-07590-1764-DECES (BOULET Jeane).jpg",
    "gv_monster": "Figure du monstre qui désole le Gevaudan.jpg",
    "gv_hyena": "Recueil Magné de Marolles - Portrait de la Hyène, Bête féroce.jpg",
    "gv_court": "Hyenne, animal féroce qui ravage le Gevaudan depuis 1764 tel qu'on l'a envoyé à la Cour - estampe - btv1b8409670k.jpg",
    "gv_estampe": "La bête de Gevaudan - estampe - btv1b8409672d.jpg",
    "gv_fight": "La-Bete 3.jpg",
    "gv_vallet": "Bête du Gévaudan combattue par Marie-Jeanne Vallet.jpg",
    "gv_london": "Gevaudanwolf.jpg",
    "gv_mandement": "Mandement de Monseigneur l'évêque de Mende.jpg",
    "gv_wolf": "Wolf of Chazes.jpg",
    "gv_shoot": "Recueil Magné de Marolles - Véritable figure de la bête féroce qui a tant ravagé le Gévaudan.jpg",
    "gv_forest": "Foret de Ténezeyre à gauche mort Bête du Gévaudan Jean Chastel Sogne d'Auvers.jpg",
    "gv_pommier": "Lisière du bois de Pommier et chemin où fut tiré le Loup des Chazes.jpg",
    "gv_margeride": "Margeride-paysage.jpg",
    "gv_margeride2": "Paysage Margeride 2007.jpg",
    "gv_stele": "Jean Chastel vainqueur de La Bête du Gévaudan sur stèle de Philippe Kaeppelin.jpg",
    "gv_statue": "Représentation de la Bête du Gévaudan à Marvejols.jpg",
    "gv_auvers": "Forêt d'Auvers.JPG",
    # --- #009 태즈메이니아 호랑이 (틸라신)
    "ty_last": "Thylacine at Beaumaris Zoo, 1936 (NS4371-1-1063).jpg",
    "ty_batty": "Wilf Batty with last wild Thylacine 2.jpg",
    "ty_yawn": "\"Benjamin\".jpg",
    "ty_pair": "Thylacinus.jpg",
    "ty_medland": "Thylacine tasmanian wolf medland.jpg",
    "ty_1928": "Thylacinus cynocephalus at Hobart Zoo 1928.jpg",
    "ty_cubs": "Thylacine cubs.jpg",
    "ty_nextday": "Tasmanian wolf.jpg",
    "ty_gould": "Thylacinus cynocephalus (Gould).jpg",
    "ty_skeleton": "Tasmanian Tiger (Thylacine) Skeletons.jpg",
    "ty_zootheque": "Thylacinus cynocephalus Zoothèque MNHN n1.jpg",
    "ty_pup": "Thylacine (Thylacinus cynocephalus) pup, Melbourne Museum.jpg",
    "ty_rugby": "View from Mt Rugby over Pandani.jpg",
    "ty_rainforest": "CSIRO ScienceImage 541 Cool Temperate Rainforest Tasmania.jpg",
    "ty_cave": "Cool Temperate Rainforest (Growling Swallet, Tasmania).jpg",
    "ty_hobart35": "Liberty Theatre - Elizabeth St, Hobart (29 June 1935).jpg",
    "ty_devil": "Sarcophilus harrisii taranna.jpg",
    # --- #010 예티
    "yt_print": "Eric Shipton yeti footprint.png",
    "yt_print2": "Yeti footprint debunked.png",
    "yt_1937": "1937 yeti footprints.png",
    "yt_portrait": "Yeti Snowman portrait.png",
    "yt_scalp": "Purported Yeti scalp at Khumjung monastery 1998.jpg",
    "yt_gompa": "Khumjung monastery.jpg",
    "yt_1921": "1921 Mount Everest expedition members (cropped).jpg",
    "yt_passport": "Tibetan passport issued to 1921 British Mount Everest reconnaissance expedition.jpg",
    "yt_khumbu": "120410 Khumbu Glacier Pano.jpg",
    "yt_rolwaling": "Rolwaling Himal Panorama.jpg",
    "yt_beding": "Rolwaling Beding.jpg",
    "yt_namche": "Namche Bazaar from above, Nepal.jpg",
    "yt_mask": "Mani Rimdu festival, Tengboche Monastery, Nepal 01.jpg",
    "yt_bear": "Himalayan brown bear at Kufri Zoo 01.jpg",
    "yt_map": "Himalyan-and-Tibetan-brown-map.jpg",
    # --- #011 저지 데빌
    "jd_1909": "Jersey Devil Philadelphia Post 1909.jpg",
    "jd_prints": "Jersey-devil-1-700x306.jpg",
    "jd_swamp": "2013-05-10 10 51 43 Dense Atlantic White Cedar swamp along the Mount Misery Trail in Brendan T. Byrne State Forest.jpg",
    "jd_pines": "2016-08-14 13 26 30 Grove of Pitch Pine along the Reed's Road Maritime Forest Trail in Island Beach State Park, New Jersey.jpg",
    "jd_river": "2024-10-08 12 55 56 View northeast across the Mullica River within Wharton State Forest ... New Jersey.jpg",
    "jd_lake": "Reflection at Lake Oswego.jpg",
    "jd_leeds": "View south along Leeds Point Rd by Leeds Point Post Office, 2021-11-06.jpg",
    "jd_almanac": "Poor Richard's Almanac, 1733, cover.jpg",
    "jd_wyvern": "Wyvern (PSF).png",
    "jd_broad": "Broad St., New Years Day, Philadelphia, PA. LCCN2014683039.jpg",
    "jd_trolley": "69thStrTerminalTurnaroundAndRear1908.jpg",
    "jd_mill": "Some of the workers (not the youngest) leaving the Coventry Co., Mill, Anthony, R.I. 6 P.M. April 16, 1909. LOC nclc.01662.jpg",
    "jd_newsboys": "Lewis Hine, Newsboys on a stoop, Wilmington, Delaware, 1910.jpg",
    "jd_owl": "Barn Owl Night Shoot (50597697573).jpg",
    "jd_crane": "Grus canadensis in flight-2618.jpg",
    "jd_kangaroo": "Eastern grey kangaroo standing in grass - DPLA - 65b9d5a7ceea97bdc1fa3ef8572241a1.jpg",
    "jd_tracks": "Deer tracks in snow on trail at McKinstry Brook WMA 2026-02-01.jpg",
    "jd_tracks2": "Roe deer tracks in snow in Tuntorp.jpg",
    # --- #012 메갈로돈
    "mg_amnh": "Megalodon American Museum Natural History-20120521-RM-225233.jpg",
    "mg_jaws": "Megalodon jaws at American Museum of Natural History.jpg",
    "mg_tooth": "Carcharodon megalodon (fossil shark tooth) (Tertiary; Beaufort, South Carolina, USA).jpg",
    "mg_teeth_cmp": "The teeth of Megalodon and great white shark.jpg",
    "mg_vertebra": "Meg bitten cetacean vertebra.jpg",
    "mg_skeletal": "Megalodon skeletal (2025).png",
    "mg_chart": "Megalodon size chart.png",
    "mg_restore": "Otodus megalodon in sea restoration.jpg",
    "mg_si": "Carcharodon megalodon SI.jpg",
    "mg_map": "Megalodon repartition.png",
    "mg_fossil": "Carcharodon megalodon (fossil shark) (Tertiary; North Carolina, USA) 2.jpg",
    # --- #013 크라켄과 대왕오징어
    "kr_mirror": "Kongespeilet.jpg",
    "kr_alecton": "Encounter with giant squid - watercolour by officers of the Alecton.jpg",
    "kr_alecton2": "French corvette Alecton attempts to capture a giant squid.jpg",
    "kr_nehlig": "Giant squid attacking a boat by Victor Nehlig.jpg",
    "kr_bathtub": "Logy Bay giant squid from The Wide World Magazine, 1899.jpg",
    "kr_bathtub2": "Logy Bay giant squid, 1873.jpg",
    "kr_tentacle": "Giant squid tentacle saved by Moses Harvey.jpg",
    "kr_harvey": "Moses Harvey.jpg",
    "kr_verrill": "Architeuthis dux Verrill 1882.jpg",
    "kr_dingle": "Giant squid stranded at Dingle, Ireland, in 1673.jpg",
    "kr_size": "Kraken size (Olaus Magnus).png",
    "kr_eye": "Giant squid - Tottori Prefectural Museum 03.jpg",
    # --- #014 플랫우즈 몬스터
    "fw_owl_front": "Front view of a barn owl - Tyto alba - in flight.jpg",
    "fw_sign": "Road sign for Flatwoods and Sutton, West Virginia, US, at night on 31 July 2023.jpg",
    "fw_meteor": "Bright Perseid Meteor (Explore) - Flickr - kees scherer.jpg",
    "fw_meteor2": "2020 Droga Mleczna i meteor.jpg",
    "fw_bolide": "Bolid1.jpg",
    "fw_oak": "2015-09-20 12 35 55 Old White Oak in the Ewing Presbyterian Church Cemetery in Ewing, New Jersey.jpg",
    "fw_chair": "Flatwoods Visitor Chair.jpg",
    "fw_owl_face": "Barn Owl, Manchester area, UK, by Andy Chilton 2016-07-06 (Unsplash).jpg",
    "fw_owl_night": "Barn Owl Night Shoot (50597697573).jpg",
    "fw_owl_claw": "Barn Owl West Acre 2.jpg",
    "fw_village": "Flatwoods West Virginia.jpg",
    "fw_sutton": "Sutton West Virginia.jpg",
    "fw_elk": "Elk river in West Virginia.jpg",
    # --- #015 추파카브라
    "ch_art": "Chupacabras.JPG",
    "ch_cemetery": "Cementerio Nuevo de Canovanas (2025)-2.jpg",
    "ch_river": "Rio Canovanas (2025).jpg",
    "ch_aerial": "Canovanas, Puerto Rico (aerial).JPG",
    "ch_alcaldia": "Alcaldia de Canovanas (2025).jpg",
    "ch_orocovis": "View of Barrio Gato, Orocovis, Puerto Rico.jpg",
    "ch_orocovis2": "Orocovis Puerto Rico.jpg",
    "ch_yunque": "El Yunque from Torre Britton, in Puerto Rico.jpg",
    "ch_yunque2": "Baño Grande en El Yunque, Puerto Rico.jpg",
    "ch_mangy": "Mangy coyote Año Nuevo State Park.jpg",
    "ch_coyote": "Coyote (53121599343).jpg",
    "ch_mite": "Itch mite (247 32A).jpg",
}


def strip(s):
    return re.sub(r"<[^>]+>", "", s or "").replace("\n", " ").strip()


def get(url, tries=4):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(10 * (k + 1))
    raise RuntimeError("unreachable")   # tries 가 0 이하일 때만 — 타입 검사기용


def main():
    import sys
    # 추가 목록: python fetch_photos.py research/016_nessie_photos.json ...  ({"키": "파일명"} 또는 {"키": {"file": "파일명", ...}})
    for extra in sys.argv[1:]:
        for k, v in json.loads(Path(extra).read_text()).items():
            PHOTOS.setdefault(k, v["file"] if isinstance(v, dict) else v)
    ROOT.mkdir(parents=True, exist_ok=True)
    cpath = ROOT / "credits.json"
    credits = json.loads(cpath.read_text()) if cpath.exists() else {}
    missing = []
    for key, name in PHOTOS.items():
        out = ROOT / f"{key}.jpg"
        if out.exists() and key in credits:
            continue
        q = urllib.parse.urlencode(dict(action="query", format="json", titles="File:" + name, prop="imageinfo",
                                        iiprop="url|size|extmetadata", iiurlwidth=1920))
        try:
            d = json.loads(get("https://commons.wikimedia.org/w/api.php?" + q))
            page = next(iter(d["query"]["pages"].values()))
            ii = page["imageinfo"][0]
        except Exception as e:      # 파일명이 틀렸거나 지워졌다 → 건너뛰고 계속 (여기서 죽으면 뒤 목록이 전부 날아간다)
            missing.append((key, name, type(e).__name__))
            print("!! 못 찾음:", key, "|", name, flush=True)
            time.sleep(2)
            continue
        m = ii["extmetadata"]
        g = lambda k: strip(m.get(k, {}).get("value"))
        lic = g("LicenseShortName")
        if not any(lic.startswith(x.strip()) for x in OK) or "NC" in lic or "ND" in lic:
            print("건너뜀 (라이선스):", key, lic)
            continue
        # 위키미디어는 원본 직접 받기를 막는다 → 표준 썸네일 폭(960/1280/1920) 주소를 직접 만든다
        step = 1920 if ii["width"] >= 1920 else (1280 if ii["width"] >= 1280 else 960)
        orig = ii["url"].split("?")[0]
        head, fname = orig.rsplit("/", 1)
        url = head.replace("/commons/", "/commons/thumb/") + f"/{fname}/{step}px-{fname}"
        if ii["width"] <= step:        # 원본보다 큰 썸네일은 만들어 주지 않는다 → 원본
            url = orig
        elif fname.lower().endswith((".tif", ".tiff")):   # TIFF 는 JPG 썸네일로
            url = head.replace("/commons/", "/commons/thumb/") + f"/{fname}/lossy-page1-{step}px-{fname}.jpg"
        print("  url:", url, ii["width"], flush=True)
        try:
            out.write_bytes(get(url))
        except Exception as e:     # 작은 원본 파일은 429로 막힐 때가 많다 → 건너뛰고 계속
            missing.append((key, name, "download " + type(e).__name__))
            print("!! 못 받음:", key, "|", name, flush=True)
            time.sleep(20)
            continue
        author = g("Artist") or "Unknown"
        author = re.sub(r"\s+", " ", author).replace(" from Colorado, USA", "").replace(" from Santa Barbara, CA, USA", "")
        credits[key] = dict(file=name, author=author[:80], license=lic, license_url=g("LicenseUrl"),
                            source=ii["descriptionurl"], description=g("ImageDescription")[:300],
                            date=g("DateTimeOriginal")[:40])
        print("받음:", key, lic, "|", author[:40])
        cpath.write_text(json.dumps(credits, ensure_ascii=False, indent=1))
        time.sleep(6)
    if missing:
        print("\n=== 못 찾은 파일 (이름을 확인해 고칠 것) ===")
        for key, name, err in missing:
            print(f"  {key}: {name}")


if __name__ == "__main__":
    main()
