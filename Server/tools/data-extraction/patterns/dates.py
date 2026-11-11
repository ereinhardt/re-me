# ---------------------------------------------------------------------------
# Language-independent parsing of dates written by the apps, e.g. Telegram's
# HTML export writes them in the language of the app:
#   "18 Mai 2026, 12:01:01"        German
#   "May 18, 2026, 12:01:01 PM"    English
#   "18 мая 2026 г., 12:01:01"     Russian
#   "2026年5月18日 12:01:01"         Chinese / Japanese
#   "18.05.2026 12:01:01 UTC+02:00"
# The order of day, month and year does not matter: the year is the 4-digit
# number, the month a month name (see LANGUAGES) or, if there is none, a
# number (year first: year-month-day, otherwise day-month-year). Without a
# UTC offset the time is interpreted as local time of this machine.
# ---------------------------------------------------------------------------
import re
import unicodedata
from datetime import datetime, timedelta, timezone

# The 12 month names per language, separated by ",", spelling variants
# (genitive, nominative, ...) by "/". Languages that write the month as a
# number (Chinese, Japanese, Korean, Vietnamese, ...) need no entry. If a word
# means different months in two languages, the language listed first wins.
LANGUAGES = {
    "en": "january, february, march, april, may, june, july, august, september, october, november, december",
    "de": "januar/jänner, februar, märz, april, mai, juni, juli, august, september, oktober, november, dezember",
    "af": "januarie, februarie, maart, april, mei, junie, julie, augustus, september, oktober, november, desember",
    "am": "ጃንዩወሪ, ፌብሩወሪ, ማርች, ኤፕረል, ሜይ, ጁን, ጁላይ, ኦገስት, ሴፕቴምበር, ኦክቶበር, ኖቬምበር, ዲሴምበር",
    "ar": "يناير/جانفي/كانون الثاني, فبراير/فيفري/شباط, مارس/آذار, أبريل/ابريل/أفريل/نيسان, مايو/ماي/أيار, يونيو/جوان/حزيران, يوليو/جويلية/تموز, أغسطس/اغسطس/أوت/آب, سبتمبر/أيلول, أكتوبر/اكتوبر/تشرين الأول, نوفمبر/تشرين الثاني, ديسمبر/كانون الأول",
    "az": "yanvar, fevral, mart, aprel, may, iyun, iyul, avqust, sentyabr, oktyabr, noyabr, dekabr",
    "be": "студзеня/студзень, лютага/люты, сакавіка/сакавік, красавіка/красавік, траўня/травень, чэрвеня/чэрвень, ліпеня/ліпень, жніўня/жнівень, верасня/верасень, кастрычніка/кастрычнік, лістапада/лістапад, снежня/снежань",
    "bg": "януари, февруари, март, април, май, юни, юли, август, септември, октомври, ноември, декември",
    "bn": "জানুয়ারী/জানুয়ারি, ফেব্রুয়ারী/ফেব্রুয়ারি, মার্চ, এপ্রিল, মে, জুন, জুলাই, আগস্ট, সেপ্টেম্বর, অক্টোবর, নভেম্বর, ডিসেম্বর",
    "ca": "gener, febrer, març, abril, maig, juny, juliol, agost, setembre, octubre, novembre, desembre",
    "cs": "ledna/leden, února/únor, března/březen, dubna/duben, května/květen, června/červen, července/červenec, srpna/srpen, září, října/říjen, listopadu/listopad, prosince/prosinec",
    "da": "januar, februar, marts, april, maj, juni, juli, august, september, oktober, november, december",
    "el": "ιανουαρίου/ιανουάριος, φεβρουαρίου/φεβρουάριος, μαρτίου/μάρτιος, απριλίου/απρίλιος, μαΐου/μάιος/μάϊος, ιουνίου/ιούνιος, ιουλίου/ιούλιος, αυγούστου/αύγουστος, σεπτεμβρίου/σεπτέμβριος, οκτωβρίου/οκτώβριος, νοεμβρίου/νοέμβριος, δεκεμβρίου/δεκέμβριος",
    "es": "enero, febrero, marzo, abril, mayo, junio, julio, agosto, septiembre/setiembre, octubre, noviembre, diciembre",
    "et": "jaanuar, veebruar, märts, aprill, mai, juuni, juuli, august, september, oktoober, november, detsember",
    "eu": "urtarrila, otsaila, martxoa, apirila, maiatza, ekaina, uztaila, abuztua, iraila, urria, azaroa, abendua",
    "fa": "ژانویه, فوریه, مارس, آوریل, مه, ژوئن, ژوئیه/جولای, اوت/آگوست, سپتامبر, اکتبر, نوامبر, دسامبر",
    "fi": "tammikuuta/tammikuu, helmikuuta/helmikuu, maaliskuuta/maaliskuu, huhtikuuta/huhtikuu, toukokuuta/toukokuu, kesäkuuta/kesäkuu, heinäkuuta/heinäkuu, elokuuta/elokuu, syyskuuta/syyskuu, lokakuuta/lokakuu, marraskuuta/marraskuu, joulukuuta/joulukuu",
    "fr": "janvier, février, mars, avril, mai, juin, juillet, août, septembre, octobre, novembre, décembre",
    "gl": "xaneiro, febreiro, marzo, abril, maio, xuño, xullo, agosto, setembro, outubro, novembro, decembro",
    "he": "ינואר, פברואר, מרץ, אפריל, מאי, יוני, יולי, אוגוסט, ספטמבר, אוקטובר, נובמבר, דצמבר",
    "hi": "जनवरी, फ़रवरी/फरवरी, मार्च, अप्रैल, मई, जून, जुलाई, अगस्त, सितंबर/सितम्बर, अक्तूबर/अक्टूबर, नवंबर/नवम्बर, दिसंबर/दिसम्बर",
    "hu": "január, február, március, április, május, június, július, augusztus, szeptember, október, november, december",
    "hy": "հունվարի/հունվար, փետրվարի/փետրվար, մարտի/մարտ, ապրիլի/ապրիլ, մայիսի/մայիս, հունիսի/հունիս, հուլիսի/հուլիս, օգոստոսի/օգոստոս, սեպտեմբերի/սեպտեմբեր, հոկտեմբերի/հոկտեմբեր, նոյեմբերի/նոյեմբեր, դեկտեմբերի/դեկտեմբեր",
    "id": "januari, februari, maret, april, mei, juni, juli, agustus, september, oktober, november, desember",
    "is": "janúar, febrúar, mars, apríl, maí, júní, júlí, ágúst, september, október, nóvember, desember",
    "it": "gennaio, febbraio, marzo, aprile, maggio, giugno, luglio, agosto, settembre, ottobre, novembre, dicembre",
    "ka": "იანვარი, თებერვალი, მარტი, აპრილი, მაისი, ივნისი, ივლისი, აგვისტო, სექტემბერი, ოქტომბერი, ნოემბერი, დეკემბერი",
    "kk": "қаңтар/қантар, ақпан, наурыз, сәуір, мамыр, маусым, шілде, тамыз, қыркүйек, қазан, қараша, желтоқсан",
    "lt": "sausio/sausis, vasario/vasaris, kovo/kovas, balandžio/balandis, gegužės/gegužė, birželio/birželis, liepos/liepa, rugpjūčio/rugpjūtis, rugsėjo/rugsėjis, spalio/spalis, lapkričio/lapkritis, gruodžio/gruodis",
    "lv": "janvāris/janvārī, februāris/februārī, marts/martā, aprīlis/aprīlī, maijs/maijā, jūnijs/jūnijā, jūlijs/jūlijā, augusts/augustā, septembris/septembrī, oktobris/oktobrī, novembris/novembrī, decembris/decembrī",
    "ms": "januari, februari, mac, april, mei, jun, julai, ogos, september, oktober, november, disember",
    "nl": "januari, februari, maart, april, mei, juni, juli, augustus, september, oktober, november, december",
    "no": "januar, februar, mars, april, mai, juni, juli, august, september, oktober, november, desember",
    "pl": "stycznia/styczeń, lutego/luty, marca/marzec, kwietnia/kwiecień, maja/maj, czerwca/czerwiec, lipca/lipiec, sierpnia/sierpień, września/wrzesień, października/październik, listopada/listopad, grudnia/grudzień",
    "pt": "janeiro, fevereiro, março, abril, maio, junho, julho, agosto, setembro, outubro, novembro, dezembro",
    "ro": "ianuarie, februarie, martie, aprilie, mai, iunie, iulie, august, septembrie, octombrie, noiembrie, decembrie",
    "ru": "января/январь, февраля/февраль, марта/март, апреля/апрель, мая/май, июня/июнь, июля/июль, августа/август, сентября/сентябрь, октября/октябрь, ноября/ноябрь, декабря/декабрь",
    "sk": "januára/január, februára/február, marca/marec, apríla/apríl, mája/máj, júna/jún, júla/júl, augusta/august, septembra/september, októbra/október, novembra/november, decembra/december",
    "sl": "januarja/januar, februarja/februar, marca/marec, aprila/april, maja/maj, junija/junij, julija/julij, avgusta/avgust, septembra/september, oktobra/oktober, novembra/november, decembra/december",
    "sr": "јануар/januar, фебруар/februar, март/mart, април/april, мај/maj, јун/јуни/jun/juni, јул/јули/jul/juli, август/avgust, септембар/septembar, октобар/oktobar, новембар/novembar, децембар/decembar",
    "sv": "januari, februari, mars, april, maj, juni, juli, augusti, september, oktober, november, december",
    "th": "มกราคม, กุมภาพันธ์, มีนาคม, เมษายน, พฤษภาคม, มิถุนายน, กรกฎาคม, สิงหาคม, กันยายน, ตุลาคม, พฤศจิกายน, ธันวาคม",
    "tr": "ocak, şubat, mart, nisan, mayıs, haziran, temmuz, ağustos, eylül, ekim, kasım, aralık",
    "uk": "січня/січень, лютого/лютий, березня/березень, квітня/квітень, травня/травень, червня/червень, липня/липень, серпня/серпень, вересня/вересень, жовтня/жовтень, листопада/листопад, грудня/грудень",
    "uz": "yanvar/январ, fevral/феврал, mart/март, aprel/апрел, may/май, iyun/июн, iyul/июл, avgust/август, sentabr/сентябр, oktabr/октябр, noyabr/ноябр, dekabr/декабр",
    # Croatian last: "listopad(a)" is October here, November in Czech/Polish.
    "hr": "siječnja/siječanj, veljače/veljača, ožujka/ožujak, travnja/travanj, svibnja/svibanj, lipnja/lipanj, srpnja/srpanj, kolovoza/kolovoz, rujna/rujan, listopada/listopad, studenoga/studenog/studeni, prosinca/prosinac",
}

# Words marking the afternoon / morning in 12-hour times (dots removed).
PM = {"pm", "午後", "下午", "오후", "μμ"}
AM = {"am", "午前", "上午", "오전", "πμ"}

TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
OFFSET = re.compile(r"(?:utc|gmt)\s*([+\-−])(\d{1,2}):?(\d{2})?")
NUMBER = re.compile(r"\d+")  # also non-Latin digits, e.g. Persian ۲۰۲۶


def _key(text):
    return unicodedata.normalize("NFKC", text).casefold()


def _words(text):
    """Runs of letters including their combining marks (Hindi, Thai, ...)."""
    return "".join(c if unicodedata.category(c)[0] in "LM" else " " for c in text).split()


def _months():
    months = {}
    for names in LANGUAGES.values():
        for number, variants in enumerate(names.split(","), start=1):
            for name in variants.split("/"):
                months.setdefault(_key(name.strip()), number)
    return months


MONTHS = _months()


def _month(words):
    """Month number of the first month name among the words (also two-word
    names such as Arabic "تشرين الأول"), or None."""
    for size in (2, 1):
        for i in range(len(words) - size + 1):
            name = " ".join(words[i:i + size])
            if name in MONTHS:
                return MONTHS[name]
            if name.startswith("ב") and name[1:] in MONTHS:
                return MONTHS[name[1:]]  # Hebrew "במאי" = "in May"
    return None


def timestamp(text):
    """Unix timestamp of a date with time in any language, or None if it
    cannot be read."""
    text = _key(text)

    tz = None
    offset = OFFSET.search(text)
    if offset:
        sign = 1 if offset[1] == "+" else -1
        tz = timezone(sign * timedelta(hours=int(offset[2]), minutes=int(offset[3] or 0)))
        text = text[:offset.start()] + " " + text[offset.end():]

    time = TIME.search(text)
    if not time:
        return None
    hour, minute, second = int(time[1]), int(time[2]), int(time[3] or 0)
    date = text[:time.start()] + " " + text[time.end():]

    words = _words(date.replace(".", ""))
    if PM.intersection(words) and hour < 12:
        hour += 12
    elif AM.intersection(words) and hour == 12:
        hour = 0

    digits = NUMBER.findall(date)
    years = [i for i, n in enumerate(digits) if len(n) == 4]
    if len(years) != 1:
        return None
    numbers = [int(n) for n in digits]
    year = numbers.pop(years[0])
    month = _month(_words(date))
    if month:
        if len(numbers) != 1:
            return None
        day = numbers[0]
    elif len(numbers) == 2:
        if years[0] == 0:
            month, day = numbers
        else:
            day, month = numbers if numbers[1] <= 12 else reversed(numbers)
    else:
        return None

    try:
        return int(datetime(year, month, day, hour, minute, second, tzinfo=tz).timestamp())
    except ValueError:
        return None
