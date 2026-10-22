# Terminų žodynas

Lithuanian glossary for translated reports (translate/glossary.py): the English term as reports
write it, the Lithuanian term the translator must use, and the explanation appended to the
translation. Drafted by Claude Code on 2026-10-22 from the Russian glossary (the same 101 terms);
every row is a draft awaiting review, and a person fluent in Lithuanian must check it
before it is relied on. The numbered headings group the rows for review and are ignored by the code.

## 1. Ataskaitos ir šaltiniai

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| SEC (draft, review pending) | JAV vertybinių popierių ir biržų komisija (SEC) | JAV akcijų rinkos priežiūros institucija. Viešosios bendrovės teikia jai ataskaitas, o ji jas skelbia sistemoje EDGAR. |
| 10-K (draft, review pending) | metinė ataskaita (10-K) | Išsami JAV bendrovės metinė ataskaita SEC su auditoriaus patikrintomis finansinėmis ataskaitomis. Pagrindinis sistemos duomenų šaltinis. |
| 10-Q (draft, review pending) | ketvirtinė ataskaita (10-Q) | Ketvirtinė ataskaita SEC. Auditorius ją tik peržiūri, bet visos nepatikrina. |
| 8-K (draft, review pending) | einamoji ataskaita (8-K) | Pranešimas apie svarbų įvykį tarp planinių ataskaitų: auditoriaus pakeitimą, didelį sandorį, vadovo pasitraukimą, ataskaitų klaidų pripažinimą. |
| 10-K/A / 10-Q/A (draft, review pending) | patikslinta ataskaita (10-K/A, 10-Q/A) | Jau pateiktos ataskaitos pataisa. Dažnai nekalta: pavyzdžiui, papildo informaciją apie vadovų atlygį (Part III). Kartais tai klaidų taisymas, ir tada ji svarbi. |
| 20-F (draft, review pending) | užsienio emitento metinė ataskaita (20-F) | Metinė ataskaita užsienio bendrovės, kurios akcijomis prekiaujama JAV. Ši sistemos versija jos neskaito. |
| NT 10-K / NT 10-Q / late filing (draft, review pending) | pranešimas apie vėluojančią ataskaitą | Bendrovė praneša, kad nespės pateikti ataskaitos laiku. Savaime tai nėra pažeidimas, bet pasikartojantis vėlavimas kelia nerimą. |
| XBRL / company facts (draft, review pending) | mašininio skaitymo ataskaitų duomenys (XBRL) | Ataskaitų skaičiai formatu, kurį skaito programa. Sistema duomenis ima iš čia, o ne iš modelio atminties. |
| fiscal year / FY (draft, review pending) | finansiniai metai (FY) | Bendrovės ataskaitiniai metai. Gali nesutapti su kalendoriniais: pavyzdžiui, baigtis rugsėjį ar lapkričio pabaigoje. |
| TTM / last twelve months (draft, review pending) | paskutiniai dvylika mėnesių (TTM) | Rodiklis už paskutinius keturis ketvirčius. Sistema jį skaičiuoja taip: paskutinė metinė ataskaita plius einamųjų metų ketvirčiai minus tie patys praėjusių metų ketvirčiai. |
| restatement / restated (draft, review pending) | ankstesnių ataskaitų taisymas (klaidų ištaisymas) | Bendrovė taiso anksčiau paskelbtus skaičius, nes jie buvo neteisingi. Rimtas ženklas tikrinant ataskaitų kokybę. |
| recast (draft, review pending) | ankstesnių duomenų pergrupavimas | Ankstesni skaičiai parodyti iš naujo dėl pasikeitusių segmentų, naujo standarto ar verslo dalies pardavimo. Tai ne klaida, o įprasta praktika. Svarbu nepainioti su ataskaitų taisymu (restatement). |
| non-reliance / Item 4.02 (draft, review pending) | pranešimas, kad ataskaitomis negalima remtis (8-K, 4.02 punktas) | Bendrovė ar auditorius praneša, kad anksčiau paskelbtomis ataskaitomis pasitikėti negalima ir jos bus pataisytos. Viena stipriausių raudonų vėliavėlių. |
| material weakness (draft, review pending) | reikšmingas vidaus kontrolės trūkumas | Pripažinimas, kad ataskaitų kontrolė gali praleisti reikšmingą klaidą. Priežastis į skaičius žiūrėti atsargiau. |
| going concern (draft, review pending) | abejonė dėl veiklos tęstinumo | Ataskaitoje tiesiai pasakyta, kad kyla reikšmingų abejonių, ar bendrovė išsilaikys dar 12 mėnesių. Vienas rimčiausių ženklų. |
| auditor change / Item 4.01 (draft, review pending) | auditoriaus pakeitimas (8-K, 4.01 punktas) | Savaime gali būti įprastas. Kelia nerimą, jei jį lydi nesutarimai su auditoriumi. |
| GAAP / non-GAAP / adjusted (draft, review pending) | US GAAP / koreguoti rodikliai (non-GAAP) | US GAAP – JAV apskaitos standartai. Koreguotus rodiklius bendrovė skaičiuoja pati, dažniausiai neįtraukdama „vienkartinių“ išlaidų, todėl jie beveik visada geresni už GAAP rodiklius. |

## 2. Pajamos, pelnas ir marža

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| revenue (draft, review pending) | pajamos | Visi pinigai iš pardavimų per laikotarpį, prieš atimant bet kokias išlaidas. |
| gross profit / gross margin (draft, review pending) | bendrasis pelnas / bendrojo pelno marža | Pajamos minus parduotų prekių savikaina. Marža – bendrojo pelno dalis pajamose: rodo, kiek lieka iš kiekvieno pardavimų dolerio prieš kitas išlaidas. |
| operating income / operating margin (draft, review pending) | veiklos pelnas / veiklos pelno marža | Pagrindinės veiklos pelnas po visų veiklos išlaidų, prieš palūkanas ir mokesčius. Marža – jo dalis pajamose. |
| net income / net margin (draft, review pending) | grynasis pelnas / grynojo pelno marža | Pelnas po visų išlaidų, palūkanų ir mokesčių. Marža – jo dalis pajamose. |
| EBIT (draft, review pending) | EBIT (pelnas prieš palūkanas ir mokesčius) | Artimas veiklos pelnui. Naudojamas EV/EBIT daugiklyje. |
| EBITDA (draft, review pending) | EBITDA (pelnas prieš palūkanas, mokesčius, nusidėvėjimą ir amortizaciją) | Veiklos pelnas plius nusidėvėjimas ir amortizacija. Apytikris pagrindinės veiklos pinigų įvertis. Neįskaito įrangos atnaujinimo išlaidų, todėl gali pagražinti vaizdą. |
| EPS / earnings per share (draft, review pending) | pelnas vienai akcijai (EPS) | Grynasis pelnas, padalytas iš akcijų skaičiaus. |
| one-off / one-time (draft, review pending) | vienkartiniai straipsniai | Pajamos ar išlaidos, kurios, pasak bendrovės, nepasikartos. Jei „vienkartinės“ išlaidos atsiranda kasmet, verta suklusti. |
| earnings quality (draft, review pending) | pelno kokybė | Kiek pelną patvirtina tikri pinigai ir kiek mažai jis priklauso nuo apskaitos įverčių bei vienkartinių poveikių. |
| operating leverage (draft, review pending) | veiklos svertas | Kai pastoviosios sąnaudos didelės, pelnas auga ir krenta greičiau nei pajamos. |
| segment (draft, review pending) | segmentas | Verslo kryptis, kurią bendrovė ataskaitose rodo atskirai (pagal produktus ar regionus). |
| cyclical (draft, review pending) | ciklinis verslas | Verslas, kurio pajamos ir pelnas stipriai priklauso nuo ekonomikos ciklo fazės (automobiliai, žaliavos, statyba). |

## 3. Pinigų srautai ir apyvartinis kapitalas

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| operating cash flow (draft, review pending) | pagrindinės veiklos pinigų srautas | Pinigai, kuriuos per laikotarpį realiai atnešė pagrindinė veikla. Jei pelnas metų metus didesnis už šį srautą, reikia išsiaiškinti kodėl. |
| capital expenditure / capex (draft, review pending) | kapitalo išlaidos (capex) | Pinigai pastatams, įrangai ir kitam ilgalaikiam turtui. |
| free cash flow / FCF (draft, review pending) | laisvasis pinigų srautas (FCF) | Pagrindinės veiklos pinigų srautas minus kapitalo išlaidos. Pinigai, kuriuos galima skirti dividendams, akcijų supirkimui ar skolai grąžinti. |
| working capital (draft, review pending) | apyvartinis kapitalas | Pinigai, įdėti į einamąją veiklą: atsargos ir klientų skolos minus skolos tiekėjams. Jo augimas laikinai „suvalgo“ pinigų srautą. |
| receivables / accounts receivable (draft, review pending) | gautinos sumos | Pinigai, kuriuos klientai skolingi bendrovei už jau parduotas prekes. Jei jos auga greičiau nei pajamos, tai gali reikšti agresyvų pardavimų pripažinimą. |
| inventories (draft, review pending) | atsargos | Prekės ir medžiagos sandėlyje. Staigus jų augimas, kai pardavimai lėti, kelia nerimą. |
| deferred revenue (draft, review pending) | atidėtosios pajamos | Pinigai, iš anksto gauti iš klientų už tai, kas dar nepristatyta. Paprastai geras paklausos ženklas. |

## 4. Skola ir likvidumas

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| net debt (draft, review pending) | grynoji skola | Skola minus pinigai. Kiek bendrovė liktų skolinga, jei visus savo pinigus skirtų skolai grąžinti. |
| leverage (draft, review pending) | skolos našta | Kokia didelė skola, palyginti su pelnu. Dažnai matuojama kaip grynoji skola / EBITDA: kiek metų tokio pelno reikia skolai grąžinti. |
| interest expense (draft, review pending) | palūkanų išlaidos | Kiek bendrovė per metus sumoka palūkanų už skolą. |
| interest coverage (draft, review pending) | palūkanų padengimas | Kiek kartų veiklos pelnas didesnis už palūkanų išlaidas. Kuo daugiau, tuo ramiau. |
| maturities / refinancing (draft, review pending) | grąžinimo terminai / refinansavimas | Kada reikia grąžinti skolą ir ar bendrovė galės vėl pasiskolinti priimtinomis sąlygomis. Grąžinimo terminai į sistemos duomenis neįkeliami. |
| liquidity / cash runway (draft, review pending) | likvidumas / pinigų atsarga | Ar pakaks pinigų einamiesiems mokėjimams. „Atsarga“ – kiek mėnesių pinigų pakaks, jei nuostoliai išliks dabartiniai. |
| cash burn (draft, review pending) | pinigų deginimas | Kiek pinigų bendrovė išleidžia daugiau, nei uždirba. Būdinga nuostolingoms augančioms bendrovėms. |

## 5. Akcijos ir akcininkai

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| market cap / market value (draft, review pending) | rinkos kapitalizacija | Akcijos kaina, padauginta iš akcijų skaičiaus: kiek rinka vertina visą nuosavą kapitalą. |
| shares outstanding / share count (draft, review pending) | apyvartoje esančių akcijų skaičius | Kiek bendrovės akcijų turi akcininkai. |
| diluted shares (draft, review pending) | akcijų skaičius, įvertinus praskiedimą | Akcijų skaičius kartu su opcionais ir kitais vertybiniais popieriais, kurie gali tapti akcijomis. |
| dilution (draft, review pending) | dalies praskiedimas | Bendrovė išleidžia naujų akcijų, ir kiekvieno akcininko dalis sumažėja. Pakartotinis praskiedimas paprastai reiškia, kad bendrovė gyvena iš akcijų pardavimo. |
| stock-based compensation / SBC (draft, review pending) | atlygis akcijomis | Darbuotojams mokama akcijomis ar opcionais. Pinigai neišeina, bet akcininkams tai tikros išlaidos: jų dalis praskiedžiama. |
| buyback / repurchase (draft, review pending) | savų akcijų supirkimas | Bendrovė perka savo akcijas rinkoje, ir likusių akcininkų dalis padidėja. Naudinga, jei kaina protinga. |
| dividend / payout ratio (draft, review pending) | dividendai / išmokų dalis | Išmoka akcininkams iš pelno. Išmokų dalis – kokia pelno dalis skiriama dividendams. Jei ji didesnė nei 100 %, dividendai mokami ne iš einamojo pelno. |
| stock split / reverse split (draft, review pending) | akcijų skaidymas / akcijų sujungimas | Skaidymas: viena akcija tampa keliomis, o dalies vertė nesikeičia. Sujungimas (atvirkštinis skaidymas): kelios akcijos tampa viena. Jį dažnai daro bendrovės, kurių kaina nukrito per žemai. |
| spin-off (draft, review pending) | verslo atskyrimas | Bendrovės dalis tampa atskira bendrove, o jos akcijos išdalijamos akcininkams. Po to akcijos kaina nukrenta atskirtos dalies verte, bet tai ne skaidymas. |

## 6. Vertinimas

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| valuation (draft, review pending) | vertinimas | Bandymas suprasti, kiek verta bendrovė, ir palyginti tai su rinkos kaina. |
| multiple / valuation multiple (draft, review pending) | daugiklis (vertinimo daugiklis) | Kainos (ar bendrovės vertės) santykis su rodikliu: pelnu, pajamomis, pinigų srautu. Leidžia greitai palyginti, kiek „brangios“ bendrovės. |
| P/E / price to earnings (draft, review pending) | P/E (kaina / pelnas) | Kapitalizacija, padalyta iš grynojo pelno: kiek metų dabartinio pelno verta bendrovė. |
| P/FCF (draft, review pending) | P/FCF (kaina / laisvasis pinigų srautas) | Kaip P/E, bet pagal laisvąjį pinigų srautą, kurį apskaitos priemonėmis pagražinti sunkiau. |
| FCF yield (draft, review pending) | laisvojo pinigų srauto pajamingumas | Laisvasis pinigų srautas, padalytas iš kapitalizacijos: kiek procentų kainos bendrovė per metus uždirba laisvaisiais pinigais. Atvirkštinis P/FCF dydis. |
| enterprise value / EV (draft, review pending) | įmonės vertė (EV) | Kapitalizacija plius skola minus pinigai: viso verslo kaina kartu su skolomis. Leidžia palyginti bendroves, kurių skola skirtinga. |
| EV/Revenue / EV/EBIT / EV/EBITDA (draft, review pending) | EV/pajamos, EV/EBIT, EV/EBITDA | Daugikliai, lyginantys įmonės vertę su jos pajamomis ar pelnu. |
| equity value (draft, review pending) | nuosavo kapitalo vertė | Įmonės vertė (EV) minus skola plius pinigai: dalis, priklausanti akcininkams. |
| value per share (draft, review pending) | vertė vienai akcijai | Nuosavo kapitalo vertė, padalyta iš akcijų skaičiaus. Ataskaitoje tai intervalas prielaidoms patikrinti, o ne tikslinė kaina. |
| DCF / discounted cash flow (draft, review pending) | diskontuotų pinigų srautų vertinimas (DCF) | Bendrovės vertė kaip būsimų laisvųjų pinigų srautų, perskaičiuotų į šiandienos vertę, suma. Labai jautrus prielaidoms. Skaičiavimą atlieka Stock Autopsy, o ne DI. |
| discount rate (draft, review pending) | diskonto norma | Reikalaujama metinė grąža, pagal kurią būsimi pinigai perskaičiuojami į šiandienos pinigus. Kuo didesnė norma, tuo mažesnė vertė. |
| terminal value / terminal growth (draft, review pending) | galutinė vertė / ilgalaikis augimo tempas | Visų pinigų srautų po prognozės metų vertė, darant prielaidą, kad augimas pastovus. Dažnai sudaro didžiąją viso vertinimo dalį, todėl labai priklauso nuo prielaidų. |
| bear case / base case / bull case (draft, review pending) | pesimistinis / bazinis / optimistinis scenarijus | Trys prielaidų rinkiniai (pajamų augimas, marža ir kt.), pagal kuriuos Stock Autopsy apskaičiuoja tris vertės įverčius. |
| implied annual return / implied return (draft, review pending) | numanoma metinė grąža | Kokią metinę grąžą gaus pirkėjas už šiandienos kainą, jei išsipildys bazinis scenarijus. Stock Autopsy randa normą, kuriai esant DCF vertė lygi kainai. Pagrindinis sistemos vertinimo skaičius. |
| what the price assumes / price assumes (draft, review pending) | ką numato kaina | Stock Autopsy (ne DI) suformuluotas sakinys: kokiai kainai, prielaidoms ir grąžai esant pirkėjas liktų laimėjęs. |
| reverse DCF (draft, review pending) | atvirkštinis DCF | Atvirkštinis uždavinys: koks turi būti pajamų augimas, kad DCF vertė būtų lygi dabartinei kainai. Jei jis didesnis už viską, ką bendrovė rodė anksčiau, kaina reikalauja per daug. |
| sensitivity (draft, review pending) | jautrumas | Kiek pasikeis vertinimas, jei vieną prielaidą (normą, augimą, maržą) pastumsime vienu žingsniu aukštyn ar žemyn. |
| CAGR (draft, review pending) | sudėtinis metinis augimo tempas (CAGR) | Pastovus metinis augimas, kuris per laikotarpį duotų tą patį rezultatą kaip faktinis. |
| hurdle rate (draft, review pending) | minimali reikalaujama grąža | Grąža, žemiau kurios investicija laikoma nepatrauklia. |
| margin of safety (draft, review pending) | saugumo marža | Skirtumas tarp vertės įverčio ir kainos. Apsaugo nuo prielaidų klaidų. |
| priced in (draft, review pending) | jau įskaičiuota į kainą | Rinkos lūkesčiai, kurie jau atspindėti dabartinėje akcijos kainoje. |

## 7. Verslas ir konkurencija

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| moat (draft, review pending) | apsauginis griovys (tvarus konkurencinis pranašumas) | Tai, kas metų metus trukdo konkurentams atimti pelną: prekės ženklas, perėjimo kaštai, tinklo efektas, mastas, patentai. |
| pricing power (draft, review pending) | kainodaros galia | Gebėjimas kelti kainas neprarandant klientų. |
| switching costs (draft, review pending) | perėjimo kaštai | Kiek klientui brangu ar sudėtinga pereiti pas konkurentą. |
| network effect (draft, review pending) | tinklo efektas | Produktas tampa vertingesnis, kai daugėja jo naudotojų. |
| economies of scale (draft, review pending) | masto ekonomija | Kuo didesnė apimtis, tuo mažesnės sąnaudos vienam produkcijos vienetui. |
| backlog (draft, review pending) | užsakymų portfelis | Užsakymai, jau gauti, bet dar neįvykdyti. |
| catalyst (draft, review pending) | katalizatorius | Įvykis, galintis gerokai pakeisti rinkos požiūrį į bendrovę: ataskaita, sandoris, reguliuotojo sprendimas. |

## 8. Pačios sistemos terminai

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| Strong case (draft, review pending) | Stiprūs argumentai | Aukščiausias komiteto verdiktas: įrodymai gerai pagrindžia investicinę tezę. Tai ne rekomendacija pirkti. |
| Conditional case (draft, review pending) | Argumentai su sąlygomis | Tezė laikosi tik tada, jei išsipildys nurodytos sąlygos. |
| Weak case (draft, review pending) | Silpni argumentai | Įrodymai tezės nepagrindžia: pavyzdžiui, verslas geras, bet kaina numato per mažą grąžą. |
| Insufficient data (draft, review pending) | Nepakanka duomenų | Pagrindinių klausimų neįmanoma išspręsti turimais duomenimis. |
| Red-flagged (draft, review pending) | Raudonos vėliavėlės | Neišspręstos rimtos problemos nusveria visa kita. |
| strong / adequate / weak / red flag (analyst verdicts; draft, review pending) | stipru / priimtina / silpna / raudona vėliavėlė | Atskirų analitikų verdiktai jų siauroje srityje. |
| confidence (draft, review pending) | pasitikėjimas | Kiek sistema tikra savo verdiktu, atsižvelgiant į duomenų spragas. Nepainioti su argumentų stiprumu. |
| from the data / calculated / assumption / unverified (draft, review pending) | iš duomenų / apskaičiuota / prielaida / nepatikrinta | Kiekvieno analitiko teiginio žyma: skaičius iš duomenų; skaičius, apskaičiuotas iš duomenų; prielaida; teiginys, kurio negalima patikrinti pagal duomenis. |
| number check (draft, review pending) | skaičių patikra | Kodas (ne modelis) sutikrina teiginių skaičius su duomenimis ir perskaičiuoja formules. Sutapimas įrodo atitiktį duomenų paketui, o ne pačių duomenų teisingumą. |
| data pack (draft, review pending) | duomenų paketas | Visi skaičiai apie bendrovę, kuriuos Stock Autopsy surinko iš SEC ir Yahoo vienai datai. Visi analitikai gauna tą patį paketą. |
| red flag / severity (draft, review pending) | raudona vėliavėlė / rimtumas (1–5) | Įtartina vieta ataskaitose ar bendrovės valdyme. Kiekviena vėliavėlė turi ir nekaltą paaiškinimą, o rimtumas 5 – aukščiausias. |
| done / failed (call status in the cost table; draft, review pending) | atlikta / nepavyko | Ar modelio iškvietimas baigėsi tinkamu atsakymu. Nepavykęs iškvietimas irgi nurodomas su kaina: atmestas atsakymas taip pat apmokamas. |

## Analitikai ir komitetas

One Lithuanian name per analyst, the same everywhere in a translation; the English name follows in
brackets only in the heading of the analyst's own section. Four analysts (earnings, moat,
management, catalysts) are not in this version yet; their names are here so a later report reads
the same.

| English | Lietuviškas terminas | Paaiškinimas |
|---|---|---|
| Business Model Analyst (draft, review pending) | Verslo modelio analitikas | Nagrinėja, kaip bendrovė uždirba ir kiek tvarios jos pajamos. |
| Earnings Analyst (draft, review pending) | Ketvirčio rezultatų analitikas | Nagrinėja ketvirtinę ataskaitą ir jos aptarimo konferencinį skambutį. Šioje versijoje neveikia: stenogramos nerenkamos. |
| Forensic Accountant (draft, review pending) | Apskaitos tyrėjas | Ieško ataskaitų kokybės ir bendrovės valdymo problemų požymių. |
| Moat Analyst (draft, review pending) | Konkurencinių pranašumų analitikas | Vertina, kas saugo verslą nuo konkurentų ir kiek ilgai ši apsauga išsilaikys. Šioje versijoje neveikia. |
| Valuation Analyst (draft, review pending) | Vertinimo analitikas | Siūlo prielaidas trims scenarijams (pagal jas Stock Autopsy skaičiuoja DCF) ir aiškina rezultatą. |
| Valuation Analyst (assumptions) (draft, review pending) | Vertinimo analitikas (prielaidos) | Pirmasis vertinimo analitiko žingsnis: prielaidos trims scenarijams, pagal kurias Stock Autopsy skaičiuoja DCF. |
| Management & Capital Allocation Reviewer (draft, review pending) | Valdymo ir kapitalo paskirstymo analitikas | Vertina vadovybę ir tai, kaip bendrovė leidžia pinigus: investicijas, įmonių pirkimus, dividendus, akcijų supirkimą. Šioje versijoje neveikia. |
| Catalyst & Risk Mapper (draft, review pending) | Katalizatorių ir rizikų analitikas | Sudaro įvykių, galinčių pajudinti kainą, ir stebėtinų signalų kalendorių. Šioje versijoje neveikia. |
| Pre-Mortem Analyst (draft, review pending) | „Išankstinio skrodimo“ analitikas | Įsivaizduoja, kad investicija po kelerių metų žlugo, ir aprašo labiausiai tikėtinas priežastis. |
| Investment Committee (draft, review pending) | Investicinis komitetas | Sintezė: sujungia analitikų išvadas, ieško prieštaravimų tarp jų ir priima galutinį verdiktą. Naujų faktų neprideda. |
