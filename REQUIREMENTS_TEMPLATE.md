# Requisits de Home Activity Manager

## 1. Objectiu

Crear una integració local de Home Assistant per centralitzar en un únic dispositiu la configuració i la gestió de cada electrodomèstic no intel·ligent o bústia. La integració pot fer servir entitats que ja existeixen a Home Assistant com a fonts de dades, especialment un sensor de potència d'un endoll intel·ligent, però la detecció del cicle o de l'arribada de correu, l'estat, la configuració i les accions han de pertànyer al dispositiu gestionat per la integració.

L'usuari no ha de necessitar crear automatitzacions o blueprints externs per detectar l'inici o el final del cicle ni per executar les accions configurades.

Les agrupacions de primer nivell són `climate`, `large_appliances`, `animal_care`, `openings`, `sun_protection` i `deliveries`. `large_appliances` reuneix rentadores, assecadores, rentaplats, neveres i congeladors; `animal_care` conté l'aquari. Cada agrupació conté classes d'aparell i, sota cada classe, les modalitats de detecció amb el seu perfil concret. Les entrades auxiliars i les accions disponibles es declaren explícitament a cada perfil; no totes estan disponibles en totes les modalitats. L'estructura ha de permetre afegir perfils futurs sense repartir condicions específiques per perfil entre els fluxos, el runtime i les plataformes d'entitats. Els petits electrodomèstics no s'ofereixen fins que tinguin una classe concreta.

## 2. Identitat del projecte

- **Nom visible**: Home Activity Manager
- **Domini**: `home_activity_manager`
- **Tipus**: integració personalitzada de Home Assistant, distribuïble amb HACS
- **Funcionament**: local; sense API externa ni credencials
- **Font d'activitat**: una entitat de Home Assistant determinada per la modalitat seleccionada
- **Agrupacions inicials**: `climate`, `large_appliances`, `animal_care`, `openings`, `sun_protection`, `deliveries`
- **Idioma font**: anglès
- **Idiomes de la interfície**: anglès, castellà i català

El domini es manté diferenciat de `appliance_cycle`, que ja fa servir una altra integració.

## 3. Gestió de dispositius

La integració ha de permetre:

- **Crear** un dispositiu per a cada electrodomèstic, amb nom i tipus propis.
- **Modificar** la configuració d'un dispositiu existent sense crear-ne un duplicat. El nom, les fonts, els valors i les accions s'han de poder canviar després de la configuració inicial, però el tipus general i la modalitat d'activitat són immutables; per canviar-los cal crear un dispositiu nou.
- **Eliminar** un dispositiu de la integració i retirar-ne les entitats del registre de Home Assistant quan ja no hi hagi cap entrada que les faci servir.
- Agrupar els dispositius individuals sota un dispositiu pare compartit per categoria general, no per perfil concret. Cada entrada de configuració correspon a una categoria i pot contenir diversos aparells. Cada aparell conserva les seves entitats, l'estat runtime i la configuració; el pare només existeix mentre hi ha almenys un aparell d'aquella categoria.
- Mantenir cada aparell i la seva configuració aïllats dels altres, encara que comparteixin la mateixa integració.
- Recuperar les entrades configurades després d'un reinici de Home Assistant.

Eliminar un dispositiu de la integració no ha d'esborrar entitats, helpers, temporitzadors ni scripts creats o gestionats per l'usuari.

## 4. Configuració de cada dispositiu

Cada dispositiu ha de tenir una configuració pròpia amb els camps següents.

### Jerarquia d'agrupacions

La jerarquia canònica de configuració és **agrupació de primer nivell → classe d'aparell → modalitat/perfil**. Aquest arbre s'ha de mantenir coherent amb `APPLIANCE_GROUPS` i els perfils registrats, i s'ha de documentar igualment al README. Els selectors del flux mostren aquests nivells en passos successius.

```text
Climatització (climate)
|-- Aire condicionat
|   |-- Sensor de contacte/obertura (air_conditioner_contact)
|   `-- Sensor de potència (air_conditioner_power)
`-- Termòstat
	`-- Entitat climate (thermostat_climate)

Grans electrodomèstics (large_appliances)
|-- Rentadora -- Sensor de potència (laundry)
|-- Assecadora -- Sensor de potència (dryer)
|-- Rentaplats -- Sensor de potència (dishwasher)
|-- Nevera
|   |-- Sensor de potència (refrigerator)
|   `-- Endoll intel·ligent (refrigerator_switch)
`-- Congelador
	|-- Sensor de potència (refrigerator)
	`-- Endoll intel·ligent (refrigerator_switch)

Cura d'animals (animal_care)
`-- Aquari
	|-- Endoll intel·ligent (aquarium_plug)
	`-- Sensor de potència (aquarium_power)

Obertures (openings)
|-- Porta
|   |-- Sensor de contacte (opening)
|   `-- Entitat cover (opening_cover)
|-- Finestra -- Sensor de contacte (opening)
`-- Accés
	|-- Sensor de contacte (access_contact)
	`-- Entitat cover principal (opening_cover)

Protecció solar (sun_protection)

`-- Tendal
	|-- Sensor de contacte (sun_protection_contact)
	`-- Entitat cover (sun_protection_cover)

Lliuraments (deliveries)
`-- Bústia
	|-- Contacte de portella (mailbox_slot)
	`-- Moviment interior (mailbox_motion)

```

Els noms entre parèntesis són identificadors de perfil, no nivells addicionals. Els perfils de rentat i refrigeració comparteixen ara `large_appliances` sense canviar els identificadors ni la configuració de cada aparell. `aquarium_plug` requereix un endoll com a font d'activitat; `aquarium_power` requereix un sensor de potència i pot tenir un endoll de control opcional. Tots dos poden exposar lectures opcionals de lluminositat, temperatura de l'aigua, pH i nivell d'aigua; la lluminositat és una lectura, no un control d'entitat `light`. Porta i finestra comparteixen el perfil de contacte `opening`; només la porta convencional ofereix també `opening_cover`, on el cover representa la mateixa porta. La classe Access ofereix el contacte `access_contact` o un cover principal `opening_cover`, amb pany opcional i sense una segona persiana associada. La persiana associada és una capacitat opcional del perfil de porta per contacte, no una classe de protecció solar. Blind deixa d'estar disponible en les noves configuracions de protecció solar, però les entrades legacy amb classe `blind` han de continuar sent editables.

### 4.1 Flux de configuració

La creació segueix la jerarquia d'agrupació, classe i modalitat definida a «Jerarquia d'agrupacions» i després presenta els passos de sensors, paràmetres i accions. En editar, el tipus i la modalitat existents es mostren fixos juntament amb el nom, i se segueix amb sensors, paràmetres i accions. Les accions compartides del grup es configuren separadament a les opcions de l'entrada agrupada.

1. **Tipus i nom**: seleccionar el tipus general i definir-ne el nom.
2. **Modalitat d'activitat**: seleccionar la font d'activitat entre les disponibles per al tipus.
3. **Sensors**: seleccionar la font d'activitat obligatòria i les entrades compatibles.
4. **Paràmetres**: mostrar els llindars, temporitzacions i opcions aplicables.
5. **Accions**: mostrar els grups d'accions disponibles, que poden quedar buits.

Els passos segueixen la navegació estàndard cap endavant dels fluxos de Home Assistant; no cal afegir controls personalitzats per tornar a pantalles anteriors. En editar, es mostra la configuració desada. La validació s'ha de mostrar al pas corresponent abans de completar el flux. Cada perfil declara les seves fonts obligatòries i opcionals, paràmetres, grups d'accions i entitats de sortida.

Després de seleccionar el tipus i la modalitat, els passos de sensors, paràmetres i accions són independents per a cada perfil (combinació de tipus i modalitat). Cada perfil té identificadors de pas, formularis, camps, selectors i labels propis. No s'han de compartir pantalles, definicions de sensors ni labels entre perfils, encara que es repeteixin; una etiqueta opcional o obligatòria s'ha d'escriure directament al formulari de cada perfil i no derivar-se de condicions dinàmiques. Es pot reutilitzar lògica interna de validació o runtime sempre que no torni a unificar les definicions visibles dels formularis.

Aquest flux és el lloc central per configurar tot el comportament propi de l'electrodomèstic. Les automatitzacions externes no poden ser un requisit de funcionament. Es poden seleccionar entitats o accions ja existents a Home Assistant, inclosos scripts com a accions opcionals, però la integració ha de controlar directament la detecció de cicle i el moment d'execució de les accions.

### 4.2 Entitats d'entrada

- **Potència**: selector d'una entitat de potència de Home Assistant; obligatori en les modalitats per potència i opcional en les altres modalitats d'aparells endollats. Cal interpretar `W`/`kW` i ignorar lectures no vàlides sense fallar.
- **Energia**: selector opcional d'un sensor d'energia existent en aparells endollats. Si es selecciona, es mostra el seu total en kWh; altrament, si hi ha potència, es calcula un total persistent. Les dues acumulacions són independents i canviar de font pot canviar el total visible; un sensor extern no disponible no provoca un canvi automàtic de font. Quan hi ha potència, el botó de reinici continua disponible amb o sense sensor extern i posa a zero el total exposat per la integració. Amb una font externa, es guarda la lectura actual com a base i els increments posteriors es mostren com a consum des del reinici; l'entitat font no s'escriu ni es modifica.
- **Sensor de contacte/obertura de l'AC**: selector obligatori només al perfil `air_conditioner_contact`; no s'ofereix als perfils `air_conditioner_power` ni `thermostat_climate`. `on` significa AC en funcionament i `off` aturat; les transicions actualitzen l'estat de funcionament.
- **Obertura de porta de nevera**: selector obligatori dels perfils `refrigerator` i `refrigerator_switch`; reflecteix l'estat de porta i inicia o cancel·la l'alarma de porta oberta.
- **Switch de nevera**: al perfil `refrigerator`, selector opcional d'un endoll intel·ligent controlable que no altera la detecció per potència. Al perfil `refrigerator_switch`, el switch és obligatori, controla l'alimentació i és també la font binària d'activitat (`on` inicia i `off` finalitza el període).
- **Arribada de correu**: `mailbox_motion` requereix un sensor binari de moviment interior i `mailbox_slot` un sensor binari a la portella d'entrada. Una transició `off`→`on` després d'haver observat `off` indica una arribada; l'estat inicial `on` no ha de generar una arribada falsa.
- **Porta principal de la bústia**: selector obligatori dels dos perfils de bústia. L'obertura neteja «pendent de recollir» i cancel·la els recordatoris.
- **Porta**: per contacte, requereix un contacte d'obertura i pot incloure un pany opcional i cap o una persiana associada. La persiana associada selecciona exactament una font (contacte o entitat `cover`), mai totes dues; el contacte de la persiana ha de ser diferent del contacte de la porta. Els selectors opcionals han de permetre esborrar la selecció directament; si se seleccionen totes dues fonts, l'usuari n'ha de poder esborrar una i continuar. En mode `cover`, l'entitat és la porta mateixa i no es mostra una segona font de persiana. Quan n'hi ha una, la porta i la persiana tenen sensors independents de durada d'obertura; el sensor de la persiana només existeix mentre hi ha una font associada.
- **Accés**: requereix un contacte (`access_contact`) o un cover principal (`opening_cover`); el pany és opcional en tots dos modes. Amb cover, només els estats estables `open` i `closed` defineixen l'estat i el període obert; `opening` i `closing` no acaben ni inicien l'interval. No s'afegeix una segona persiana associada.
- **Pany i persiana associada**: els hooks de pany bloquejat/desbloquejat i persiana oberta/tancada només s'executen en canvis d'estat estables de la font configurada. Un cover que es mou no es considera encara obert o tancat.
- **Obertura de porta per a bugaderia**: selector opcional per a rentadora, rentaplats i assecadora; activa estat de porta i «pendent de buidar».
- **Switch intel·ligent de l'endoll**: selector opcional en aparells endollats. La integració n'exposa el control; només determina l'activitat si és la font seleccionada.
- **Aquari**: `aquarium_plug` requereix un switch/endoll com a font d'activitat; `aquarium_power` requereix un sensor de potència i admet un endoll de control opcional. Ambdós perfils admeten un sensor opcional d'energia acumulada i lectures opcionals d'il·luminància, temperatura de l'aigua, pH i nivell d'aigua. Sense sensor acumulat, el total es calcula a partir de la potència quan el perfil la té configurada.

Les fonts obligatòries depenen de la modalitat seleccionada. La categoria termòstat ofereix contacte/obertura, potència i `climate`; el contacte és obligatori només en la modalitat de contacte. Només la font seleccionada determina l'activitat. No es requereixen helpers externs: la integració proporciona les entitats de sortida de la secció 5. Les fonts seleccionades són externes i mai no s'han d'esborrar ni canviar de propietat d'integració. La regla de representació i duplicació de la secció 5 s'aplica a tots els dominis i perfils. Els inputs usats només internament, com el moviment d'arribada de la bústia, no es mostren ni s'associen al dispositiu HAM. En descarregar o retirar la configuració, es desfà una associació directa només si l'entitat encara és al dispositiu HAM.

### 4.3 Detecció del cicle per potència

Tots els paràmetres de durada configurables s'expressen en segons. Els valors s'han de poder ajustar individualment per dispositiu, però no és obligatori modificar-los. La integració els aplica automàticament quan es crea el dispositiu. Els valors per defecte són els mostrats a les captures:

| Paràmetre | Valor inicial | Unitat | Comportament |
| --- | ---: | --- | --- |
| Llindar de potència d'inici | 4 | W | La potència ha de superar el llindar durant la histèresi d'inici per considerar que l'aparell ha començat. |
| Histèresi d'inici | 15 | s | Temps durant el qual la potència s'ha de mantenir per sobre del llindar d'inici. |
| Llindar de potència de finalització | 1 | W | La potència ha de baixar del llindar durant la histèresi de finalització per considerar que l'aparell ha acabat. |
| Histèresi de finalització | 60 | s | Temps durant el qual la potència s'ha de mantenir per sota del llindar de finalització. |
| Temps màxim de funcionament | buit | s | Opcional; buit desactiva l'avís de temps màxim. |

La configuració ha d'evitar canvis d'estat repetits per oscil·lacions breus de potència. Un cop iniciat un cicle, lectures entre els llindars d'inici i finalització no l'han de marcar com acabat. La validació ha d'impedir una configuració incoherent en què el llindar de finalització sigui igual o superior al d'inici.

Cada dispositiu pot tenir un **temps màxim de funcionament** configurable en segons. Si no s'especifica cap valor, aquesta protecció queda desactivada. El temps es compta des de l'inici confirmat del cicle. En superar-lo, la integració ha d'executar una sola vegada les accions de temps màxim configurades per a aquell cicle, si n'hi ha. La superació del límit no ha de marcar per si sola el cicle com a acabat ni apagar automàticament l'endoll; qualsevol apagada s'ha de configurar explícitament com una acció.

### 4.4 Perfils de tipus i comportaments addicionals

Els tipus s'han de definir en un registre de perfils extensible. Cada perfil declara fonts d'entrada, grups de paràmetres, grups d'accions, capacitats i entitats de sortida. Els fluxos i les plataformes han de derivar-ne els camps visibles; no han d'acumular condicions específiques disperses per nom de tipus. Els perfils de rentadora, rentaplats i assecadora es mantenen separats encara que facin servir avui els mateixos detectors i grups. Afegir un tipus nou que faci servir una estratègia existent ha de requerir registrar-ne el perfil i traduccions; només una estratègia nova requereix un detector nou.

- **Aire condicionat per sensor de contacte/obertura** (`air_conditioner_contact`): el sensor és la font binària de funcionament. Les transicions `off`→`on` i `on`→`off` inicien i finalitzen respectivament el període actiu. La potència i l'energia són opcionals; no es creen «pendent de buidar» ni temps restant estimat.
- **Aire condicionat per potència** (`air_conditioner_power`): usa llindars/histèresi de potència per detectar activitat. No es creen «pendent de buidar» ni temps restant estimat.
- **Termòstat per entitat `climate`** (`thermostat_climate`): requereix una entitat `climate` existent. Si l'entitat no té dispositiu, s'associa directament al dispositiu gestionat i no es crea una segona entitat. Si ja té dispositiu, aquest no es modifica i es crea un proxy nadiu al dispositiu gestionat que reflecteix l'estat i els controls estàndard i els reenvia a l'entitat original. En tots dos casos, l'entitat continua pertanyent a la integració d'origen. L'activitat segueix el mode de la climate (`off` versus qualsevol mode actiu), també quan `hvac_action` és inactiu.
- **Nevera per potència** (`refrigerator`): requereix sensor de potència i contacte de porta. La potència detecta activitat del compressor i el contacte detecta l'obertura. Pot incloure opcionalment un switch intel·ligent controlable, que no canvia la detecció per potència ni genera alarmes si s'apaga. Les accions d'inici/final segueixen l'activitat del compressor. No s'hi creen «pendent de buidar» ni temps restant estimat. Només s'ofereix l'alarma configurable de porta oberta.
- **Nevera per interruptor** (`refrigerator_switch`): requereix un interruptor intel·ligent que controla l'alimentació i és la font binària d'activitat; també requereix un contacte separat de porta. `on` inicia i `off` finalitza el període actiu i executa les accions corresponents. La potència i l'energia són opcionals; no es creen temps restant ni alarmes d'endoll apagat o compressor inactiu. Manté l'alarma configurable de porta oberta.
- **Aquari** (`aquarium_plug`, `aquarium_power`): l'endoll o el sensor de potència seleccionat determina l'activitat. Els sensors opcionals de lluminositat, temperatura de l'aigua, pH i nivell d'aigua només proporcionen lectures i no alteren la detecció.
- **Bústia amb moviment** (`mailbox_motion`): el moviment interior detecta l'arribada de correu. La porta principal és independent del sensor d'arribada i neteja l'estat pendent quan s'obre.
- **Bústia amb portella** (`mailbox_slot`): un sensor de contacte/obertura de la portella d'entrada detecta l'arribada de correu. La porta principal és independent d'aquest sensor i neteja l'estat pendent quan s'obre.
- En tots dos perfils de bústia, una arribada posa «pendent de recollir» a `on`, reinicia el recompte i activa les accions d'arribada. Els recordatoris configurats només s'inicien quan la porta principal consta tancada; si el correu arriba amb la porta oberta, es programen quan aquesta es tanca. El sensor d'arribada no s'interpreta com un inici o final de cicle.
- **Alarma de porta de nevera**: retard per defecte de 120 s; després de l'avís inicial es repeteix cada 900 s fins a 3 repeticions addicionals. Tancar la porta rearma l'alarma.
- Els temporitzadors i recomptes d'alarmes es persisteixen i es restauren sense ràfegues després d'un reinici. Una transició `unknown`/`unavailable` no es considera resolució ni genera una alarma falsa.

### 4.5 Accions

Cada dispositiu pot tenir llistes locals d'accions de Home Assistant configurables i editables, compatibles amb les accions estàndard de Home Assistant. L'usuari ha de poder afegir, eliminar i reordenar diverses accions. Les llistes poden quedar buides sense impedir que el dispositiu detecti i mostri els cicles. A més, cada entrada agrupada pot tenir llistes d'accions compartides pels seus dispositius.

Les accions configurables al nivell d'agrupació són la unió ordenada dels grups d'acció (`action_groups`) dels perfils descendents de `APPLIANCE_GROUPS`. Un hook s'ofereix si almenys un perfil del grup el suporta. En runtime, cada appliance només l'executa si el seu perfil el declara, la capacitat corresponent està configurada i la seva pròpia entitat emet el canvi pertinent; no es tracta d'una difusió de l'acció a tots els membres. Això permet oferir pany bloquejat/desbloquejat i persiana oberta/tancada al grup `openings` sense executar-los als perfils que no tenen aquests inputs. Els hooks particulars continuen configurant-se localment a l'appliance, amb camps condicionats a la capacitat configurada. Les opcions globals obsoletes o no suportades no s'han d'executar.

En migrar les antigues agrupacions `laundry` i `refrigeration` a `large_appliances`, les llistes de `group_actions` es combinen per clau i es dedupliquen sense canviar l'ordre. Així es conserven, per exemple, `pending_actions` i `emptied_actions` de bugaderia encara que el grup nou també contingui neveres. Les accions es mantenen a nivell de grup; cada runtime les filtra segons `action_groups` del perfil, de manera que una nevera no executa accions de buidatge i una rentadora no executa l'alarma de porta de nevera.

Quan es produeix un hook per a un appliance, s'executen primer les accions compartides del grup i després les accions locals d'aquell appliance. Les accions compartides s'executen per cada appliance i el seu propi esdeveniment, no una única vegada coordinada per a tot el grup. Una llista local buida no desactiva les accions globals. Les opcions globals s'han de conservar en editar o eliminar un dispositiu membre mentre l'entrada de grup continuï existint.

Les accions compartides no defineixen un calendari ni un recompte de repeticions globals. Cada hook es desencadena segons la font d'activitat pròpia del dispositiu i els paràmetres aplicables. Quan un hook depèn de temporitzadors o recomptes, cada dispositiu aporta els seus: les accions de temps màxim només s'activen si aquell dispositiu té un temps màxim configurat; els recordatoris pendents fan servir el seu retard, interval i màxim de repeticions; les alarmes de porta i compressor fan servir els retards, intervals i límits propis del dispositiu; l'alarma d'endoll s'activa immediatament i fa servir el seu interval i límit de repeticions. Aquests valors es configuren als paràmetres del dispositiu, no a les opcions d'accions de l'agrupació. El recompte indica repeticions addicionals després de l'execució inicial: amb 3 repeticions addicionals es permeten fins a 4 execucions totals per dispositiu. La UI i el README han d'explicar aquest comportament per als hooks corresponents.

Les plantilles de les accions compartides reben `ham_device_name`, el nom del dispositiu gestionat, i `ham_device_area_name`, la seva àrea assignada o `None` si no n'hi ha. Aquests valors descriuen el dispositiu de l'acció, no l'entitat que l'ha desencadenada. Quan una entitat d'entrada configurada provoca l'acció, `ham_source_entity_id` conté l'ID d'aquesta entitat original, no el del wrapper de la integració. Les accions iniciades per temporitzador no defineixen `ham_source_entity_id`. Per exemple, `{{ ham_device_area_name or ham_device_name }}` mostra l'àrea i, si no n'hi ha, el nom del dispositiu; `{{ ham_source_entity_id | default('temporitzador', true) }}` mostra l'entitat d'origen o «temporitzador». Els noms anteriors `ham_appliance_name` i `ham_area_name` continuen disponibles com a àlies. Aquestes variables s'han de passar a cada execució, diferenciades per appliance.

- **Accions en finalitzar l'activitat**: s'executen quan la font de detecció confirma que l'activitat s'ha aturat. En neveres per potència, això correspon a l'aturada del compressor; en neveres per interruptor, a passar el switch a `off`.
- **Accions en iniciar l'activitat**: s'executen quan la font de detecció confirma que l'activitat ha començat. En neveres per potència, això correspon a l'inici del compressor; en neveres per interruptor, a passar el switch a `on`. Exemples: enviar una notificació, anunciar un missatge de veu o iniciar un temporitzador.
- **Accions en superar el temps màxim**: s'executen una sola vegada quan un cicle actiu supera el temps màxim configurat. Exemple: enviar una notificació. Aquest grup és independent de les accions de finalització.
- **Accions mentre està pendent de buidar**: grup opcional disponible quan s'ha configurat un sensor de porta. En finalitzar el cicle, si «pendent de buidar» continua `on`, s'espera l'interval configurat abans de la primera execució. Després es repeteixen cada X segons mentre la porta continuï tancada i no s'hagi assolit el màxim; cada interval de repetició es compta des que acaba l'execució anterior. L'interval X ha de ser un nombre enter positiu i el nombre màxim de repeticions un enter no negatiu; els valors per defecte són 900 segons (15 minuts) i 3 repeticions. El límit compta només les execucions posteriors a la inicial; amb 3 repeticions, hi ha com a màxim 4 execucions en total. En obrir-se la porta, l'estat es neteja i les accions pendents es cancel·len immediatament. En assolir el màxim, les repeticions s'aturen encara que la porta continuï tancada i «pendent de buidar» es manté `on` fins que s'obri.
- **Alarma d'endoll apagat**: disponible només en perfils que declarin aquesta capacitat. Les neveres no ofereixen aquesta alarma; l'endoll intel·ligent de la nevera per potència és únicament un control opcional.
- **Alarma de porta de nevera**: acció pròpia del tipus nevera, disponible amb contacte configurat; s'executa després del retard de porta oberta i repeteix segons els paràmetres del perfil fins al màxim. Tancar la porta rearma el grup.
- **Arribada de correu**: acció pròpia dels perfils de bústia, executada en detectar una arribada. Les accions de «pendent de recollir» segueixen el retard, interval i màxim de repeticions configurats, i es cancel·len en obrir-se la porta principal.

Les accions locals són configuració de cada dispositiu i les globals són configuració explícita de l'agrupació; no s'han de codificar com a scripts fixos ni compartir implícitament. La integració les ha d'executar directament en l'ordre configurat quan detecti els canvis de cicle o de porta, sense dependre d'una automatització o blueprint extern. No s'han de solapar dues execucions del mateix hook per appliance. Es poden invocar scripts existents si l'usuari els selecciona, però no són obligatoris. Els errors d'una acció s'han de registrar sense interrompre la resta d'accions ni la detecció de cicles, i sense exposar dades sensibles.

## 5. Entitats i associació amb el dispositiu

- Cada electrodomèstic configurat ha d'aparèixer com un dispositiu propi al registre de dispositius de Home Assistant.
- Els dispositius comparteixen un dispositiu pare per categoria general, no per perfil concret. El pare no conté entitats pròpies; cada aparell continua tenint el seu dispositiu independent com a fill. Només es registren categories amb aparells configurats i desapareixen en eliminar l'últim aparell de cada categoria.
- Totes les entitats de sortida creades per la integració han d'estar associades al dispositiu de l'electrodomèstic i ser visibles des de la seva pàgina.
- **Definició de HAM Proxy**: un HAM Proxy és una segona entitat creada per la integració per representar una font externa al dispositiu de l'aparell, mentre conserva intacta l'entitat original. Només hi ha proxy quan HAM duplica l'entitat; el domini o el sufix no converteixen per si sols una sortida en proxy. Per defecte, el nom visible de cada còpia acaba en ` (HAM Proxy)` i el seu `entity_id` en `_ham_proxy`. Si la font té nom personalitzat, s'utilitza; si no, s'utilitza el nom original de la integració; si tampoc no en té, s'utilitza el fallback traduït. Quan l'entitat és al registre sense nom personalitzat ni original, no s'ha d'utilitzar el seu `friendly_name` d'estat com a nom font, perquè Home Assistant pot haver-hi incorporat també el nom del dispositiu. Els usuaris poden canviar aquests valors després de crear-se.
- **Regla d'associació i duplicació de fonts visibles**: per a cada input que el perfil declara representable a la UI, si l'entitat font no té dispositiu pare, s'associa directament al dispositiu HAM i no se'n crea una còpia. Si ja pertany a un altre dispositiu, la font conserva aquesta associació i HAM crea un proxy visible al dispositiu de l'aparell. Aquesta regla inclou sensors, interruptors, contactes i entitats natives `climate`, `cover` i `lock`; la font continua pertanyent a la seva integració d'origen. Una entrada que el perfil usa només per a càlculs interns i no mostra a la UI no s'associa ni genera proxy. Les sortides calculades per HAM, com «En funcionament», durades, estats pendents, botons i energia acumulada local, no són proxies.
- **Excepció d'energia acumulada externa**: quan se selecciona un sensor extern d'energia acumulada, HAM crea sempre una entitat proxy d'energia, encara que la font no tingui dispositiu pare. La còpia mostra el valor en kWh ajustat amb la base de reinici local; la font original no es reassigna ni s'escriu. Si l'energia es calcula localment a partir de potència perquè no s'ha seleccionat font acumulada, la sortida no és proxy.
- **Cicle de vida i representació**: les fonts originals mai no s'esborren. En descarregar o retirar la configuració, HAM desfà només les associacions directes que encara apunten al dispositiu HAM i retira els proxies obsolets propis. Els proxies visibles per defecte respecten les preferències d'ocultació de l'usuari. Les còpies font-backed reflecteixen canvis, `unknown`, `unavailable`, desaparició i recuperació; les entitats de control reenvien les ordres suportades a la font. L'AC per contacte es representa amb l'estat «En funcionament» i no duplica el seu sensor d'entrada; el moviment de bústia només s'utilitza internament. Les sortides «Porta», «Portella» i altres sortides declarades conserven la semàntica del perfil i només són proxy quan realment dupliquen una font per mantenir-la al dispositiu original.
- **Actualització dels wrappers**: cada wrapper declarat pel perfil ha d'actualitzar el valor quan canvia la seva font, incloent-hi `unknown`, `unavailable`, desaparició i recuperació. Una font `unknown` es representa com a desconeguda; una font `unavailable` o absent, com a no disponible. Els valors de potència i energia es normalitzen a W i kWh. L'última potència vàlida pot conservar-se internament, però no s'ha de mostrar com a lectura actual mentre la font és desconeguda o no disponible. La detecció i la persistència del cicle continuen independents d'aquesta representació.
- **Potència** i **Energia total consumida**: es creen segons les entrades configurades, independentment de la modalitat. L'energia es mostra en kWh, des d'un sensor extern o calculada i persistent a partir de potència.
- **Reinici de l'energia exposada**: si el perfil exposa energia total i hi ha un sensor de potència configurat, es crea un botó per posar a zero el total visible de la integració. Amb energia local, reinicia l'acumulació calculada. Amb un sensor extern seleccionat, fixa una base a la lectura actual i mostra els increments posteriors; no modifica ni escriu a l'entitat externa. La base es conserva després de reiniciar Home Assistant i s'aplica només a la mateixa entitat font.
- **Durada de l'últim període actiu**: sensor de sortida amb la durada del període d'activitat més recent detectat.
- **Durada d'obertura**: les etiquetes dels sensors indiquen explícitament el temps durant el qual cada element ha romàs obert. Mesuren l'interval en estat estable obert, no el temps que ha trigat el motor a obrir.
- **Durada d'obertura**: les etiquetes dels sensors indiquen explícitament que mesuren l'últim període complet en què cada element ha estat obert. Mentre l'element continua obert, es conserva el valor del període completat anterior; abans del primer tancament, el valor és desconegut. Mesuren l'interval en estat estable obert, no el temps que ha trigat el motor a obrir.
- **Temps restant estimat**: només es crea per perfils de cicle que en poden oferir una estimació útil. No es crea per AC ni nevera.
- **Estat (funcionament)**: cada aparell elèctric té una entitat binària pròpia que indica si hi ha activitat segons l'estratègia declarada pel perfil, separada dels wrappers d'entrada i amb identificador estable.
- **Estat i durada (obert/tancat)**: les entitats binàries de porta, finestra, Access i tendal han d'identificar la classe: «Estat de la porta», «Estat de la finestra», «Estat de l'accés» i «Estat del tendal», respectivament. Una persiana associada s'ha d'anomenar «Estat de la persiana», separada de l'estat principal. Aquests noms han d'estar traduïts a tots els idiomes de la interfície. Cada capa té la seva durada d'obertura independent, mesurada entre estats estables `open` i `closed`; `opening` i `closing` conserven l'estat anterior. La durada d'Access amb cover és el temps que l'obertura roman oberta, no el temps de funcionament del motor. La durada de persiana només s'exposa si hi ha una font de persiana associada i es restaura després de reiniciar Home Assistant.
- **Porta**: si el perfil usa un contacte de porta, entitat binària de sortida que en reflecteix l'estat.
- **Portella de bústia**: només per a `mailbox_slot`, entitat binària de sortida que reflecteix si el contacte de la portella d'arribada és obert o tancat. És diferent de l'entitat Porta, que representa l'obertura de la porta principal per recollir el correu.
- **Pendent de buidar/recollir**: per als perfils de bugaderia amb sensor de porta i per als perfils de bústia; mai per AC o nevera.
- **Ocupació de la bústia**: «Ocupada» indica que hi ha correu pendent de recollir; és independent de l'estat obert/tancat de la portella i de la porta principal.
- **Neteja manual de l'estat pendent**: quan un dispositiu té un estat «pendent de buidar», la integració ha de crear-hi també un botó propi per posar-lo manualment a `off`, independentment dels sensors. Aquesta acció de recuperació ha de funcionar encara que el sensor associat falli o no estigui disponible, i ha de cancel·lar els recordatoris pendents i reiniciar-ne el recompte.
- **Endoll**: si el perfil admet un switch intel·ligent i se n'ha seleccionat un, entitat de switch associada que en reflecteix l'estat i permet activar-lo o desactivar-lo. Al perfil `refrigerator`, és opcional i no substitueix la detecció per potència; al perfil `refrigerator_switch`, és obligatori i també és la font de detecció d'activitat.
- **Entitats d'alarma**: les alarmes de nevera es representen amb els grups d'acció i els sensors d'estat declarats pel perfil; no es creen entitats de bugaderia per reaprofitar-les.
- Quan hi ha sensor d'obertura, «Pendent de buidar» passa a `on` en iniciar un cicle i es manté en acabar-lo, fins que el sensor físic indiqui que la porta s'ha obert; llavors passa a `off`. No s'ha de reiniciar només perquè el cicle hagi acabat. En una bústia, «Pendent de recollir» passa a `on` en detectar correu i a `off` en obrir la porta principal. Sense sensor d'obertura no es creen les entitats Porta ni Pendent.
- Un switch auxiliar a `off` no finalitza el període actiu; només ho fa quan el switch és la font d'activitat seleccionada.
- En iniciar un cicle, el temps restant estimat és la durada de l'últim cicle completat menys el temps transcorregut des de l'inici del cicle actual. S'ha d'actualitzar durant el cicle i no pot baixar de zero.
- Si encara no s'ha completat cap cicle, el temps restant estimat ha de ser desconegut/no disponible, no un valor inventat. L'estimació es basa només en l'últim cicle completat i s'ha d'identificar com a estimació, no com a mesura garantida.
- El sensor de potència i el sensor d'obertura seleccionats continuen sent les fonts de dades originals; les entitats de sortida i la gestió del cicle queden centralitzades al dispositiu de l'electrodomèstic.
- No s'han de crear helpers, scripts ni automatitzacions externes per representar estats o fer funcionar la lògica essencial de la integració.
- El nom i el tipus de cada aparell han de ser visibles i distingibles quan hi ha més d'un dispositiu configurat.
- Els identificadors d'entitat han de ser estables davant de canvis de llindars, accions o altres opcions.

## 6. Persistència i actualitzacions

- La configuració de dispositius, entitats vinculades, llindars, histèresis i accions s'ha de desar a les entrades de configuració de Home Assistant.
- La migració de configuracions antigues ha de fusionar les entrades de rentat i refrigeració en `large_appliances` sense perdre accions compartides, opcions locals, identificadors d'aparell, entitats, personalitzacions del registre ni estat runtime. Les llistes d'accions compartides amb contingut duplicat es desen una sola vegada.
- La integració ha de persistir l'estat actiu del cicle, les marques temporals d'inici i dels temporitzadors d'histèresi, l'energia acumulada, la durada de l'últim cicle completat, l'estat «pendent de buidar», el nombre de repeticions ja executades i la data/hora prevista del proper avís.
- En reiniciar Home Assistant, s'ha de restaurar aquest estat i calcular els temps transcorreguts a partir de les marques temporals guardades; no s'han de reiniciar el cicle, el temps màxim, l'estimació de temps restant ni els intervals d'avís. Les accions d'inici del cicle ja executades no s'han de repetir.
- Després de restaurar, la integració ha de tornar a subscriure's a les entitats d'entrada i comprovar-ne l'estat actual. Si la porta és oberta, ha de netejar «pendent de buidar» i cancel·lar els avisos pendents. Si una entitat encara no està disponible, ha de conservar l'estat restaurat i esperar que torni a estar disponible, sense inferir una finalització.
- Si un avís de «pendent de buidar» ha vençut mentre Home Assistant era aturat i la porta continua tancada, es pot executar un únic avís de recuperació immediat; s'han d'ometre altres intervals vençuts sense enviar una ràfega i reprendre la cadència a partir del proper venciment futur. L'avís de recuperació compta dins del màxim configurat.
- El temps màxim configurat i l'estat d'avís ja executat del cicle actual s'han de conservar després d'un reinici, per evitar perdre el límit o repetir l'acció d'avís.
- Modificar una opció ha d'actualitzar només el dispositiu afectat i les seves entitats.
- La integració ha d'actualitzar-se davant de canvis de les entitats d'entrada sense fer sondeig de xarxa innecessari.
- Si una entitat seleccionada desapareix o queda no disponible, el dispositiu ha de continuar carregat i crear un issue de Repairs per a l'entitat. En recuperar-se, l'issue s'ha d'eliminar.

## 7. Seguretat i privadesa

- No es recullen ni s'envien dades a serveis externs.
- No es demanen credencials.
- Les accions només s'executen en resposta als canvis de cicle del dispositiu i segons la configuració de l'usuari.
- Els errors i registres no han d'incloure dades personals innecessàries.

## 8. Criteris d'acceptació

1. Es poden crear dos o més electrodomèstics i cadascun té dispositiu, valors i accions independents.
2. Es poden modificar i eliminar dispositius des de Home Assistant sense perdre ni esborrar entitats externes seleccionades.
3. Amb els valors inicials dels perfils de potència, l'activitat comença quan se supera 4 W durant 15 segons i acaba quan baixa d'1 W durant 60 segons; un switch auxiliar no altera el cicle.
4. Els valors de llindar i histèresi es poden editar per dispositiu i persisteixen després de reiniciar Home Assistant.
5. Tots els perfils amb cicle exposen les mateixes accions d'inici i de final del cicle, sense etiquetar-les segons l'entitat o font que detecta l'activitat. S'executen separadament, en l'ordre configurat, i poden incloure notificacions, missatges de veu i operacions de temporitzador.
6. Els selectors d'entrada obligatòria i opcional corresponen al perfil triat; es pot crear un AC per contacte sense potència ni un AC per potència sense contacte.
7. El dispositiu exposa potència i energia segons les entrades seleccionades; no hi ha «Pendent de buidar» ni «Temps restant estimat» en AC o nevera.
8. En rentadora, rentaplats i assecadora, quan hi ha sensor de porta, «Pendent de buidar» passa a `on` en iniciar el cicle, es manté quan acaba i només torna a `off` quan s'obre la porta.
9. Cada dispositiu que tingui «Pendent de buidar» exposa un botó propi per posar l'estat a `off` manualment i cancel·lar els avisos; en una bústia, aquesta acció també acaba el cicle i executa les accions de final.
10. L'energia calculada s'acumula durant la vida del dispositiu i es conserva després de reiniciar Home Assistant. Amb sensor de potència, el botó de reinici existeix tant si hi ha un sensor extern seleccionat com si no i posa a zero el total exposat. Amb una font externa, aquesta no canvia: es guarda la lectura existent com a base i només es mostren els increments posteriors. La base es restaura després d'un reinici i no es reutilitza si canvia la font.
11. En iniciar un nou cicle després d'haver-ne completat un, el temps restant comença a partir de la durada de l'últim cicle i es redueix segons el temps transcorregut del cicle actual.
12. Abans de disposar d'un cicle completat, el temps restant és desconegut/no disponible; no es mostra una estimació fictícia.
13. Si Home Assistant es reinicia durant un cicle, l'estat de funcionament continua actiu, la durada i el temps restant es calculen des de les marques temporals originals i no es repeteixen les accions d'inici ja executades.
14. Una lectura de potència invàlida no provoca una fallada de la integració. Si una entitat d'entrada configurada falta o és `unknown`/`unavailable`, la integració continua carregada i crea un avís de Repairs per a aquella entitat; quan torna a estar disponible, elimina l'avís.
15. Els canvis breus de potència no generen inicis o finalitzacions falsos si no es compleix la histèresi corresponent.
16. Quan s'ha configurat un temps màxim, en superar-lo s'executen una sola vegada les accions específiques d'avís; el cicle no es dona per acabat ni l'endoll s'apaga automàticament.
17. Si hi ha accions de «pendent de buidar», la primera s'executa 900 segons (15 minuts) després de finalitzar el cicle, només si l'estat continua actiu; després es repeteixen cada X segons fins al màxim o fins que s'obre la porta.
18. El nombre màxim compta les repeticions posteriors a l'execució immediata inicial; amb el valor per defecte de 3, les accions s'executen com a màxim 4 vegades.
19. El retard inicial per defecte i l'interval per defecte entre repeticions són de 900 segons (15 minuts), modificables per dispositiu.
20. En assolir el màxim, les repeticions s'aturen però «pendent de buidar» continua actiu fins que s'obre la porta.
21. Si una acció periòdica dura més que l'interval configurat, no se solapa una segona execució del mateix grup; el següent interval comença quan acaba l'execució anterior. La finalització d'una acció de recordatori o alarma obsoleta no modifica l'estat ni els venciments d'una condició posterior.
22. Si Home Assistant es reinicia mentre «pendent de buidar» és actiu, l'estat i el nombre de repeticions es restauren; es respecta el proper venciment i, si ja ha passat, s'executa com a màxim un avís de recuperació sense superar el límit ni crear una ràfega.
23. Es pot completar la configuració amb nom, tipus i sensor de potència, sense sensor de porta ni switch, deixant el temps màxim i les accions buits i mantenint els llindars per defecte.
24. La creació mostra cinc passos: tipus/nom, modalitat, sensors, paràmetres i accions. En editar es mostren tipus i modalitat fixos amb el nom, seguits de sensors, paràmetres i accions.
25. Si es configura un switch intel·ligent, el seu estat es reflecteix i es pot controlar des de la pàgina del dispositiu; si no se'n configura cap, la integració funciona igualment sense crear aquesta entitat.
26. Un dispositiu funciona amb la seva configuració pròpia sense que l'usuari hagi de crear automatitzacions, blueprints o helpers externs per detectar cicles, representar-ne l'estat o executar les accions.
27. Una acció fallida no impedeix executar les accions posteriors ni altera la detecció del cicle.
28. Tots els textos visibles de la interfície tenen traducció completa en anglès, castellà i català.
29. Les propostes de nova icona són `docs/home_activity_manager_icon_option_1.svg` i `docs/home_activity_manager_icon_option_2.svg`. Cal escollir-ne una abans de substituir la icona de marca actual.
30. Les modalitats de la categoria termòstat requereixen la font seleccionada i només mostren les entrades declarades al perfil: el contacte/obertura és obligatori al perfil `air_conditioner_contact` i no apareix als perfils `thermostat_climate` ni `air_conditioner_power`; `thermostat_climate` requereix una entitat `climate`.
31. Els perfils d'AC no creen «Pendent de buidar» ni «Temps restant estimat»; potència i energia depenen de les entrades seleccionades.
32. La nevera per potència (`refrigerator`) exigeix potència i contacte de porta, admet un switch de control opcional sense substituir la detecció per potència, crea estat de funcionament i porta, executa les accions comunes d'inici/final quan comença i s'atura el cicle del compressor, no crea «Pendent de buidar» ni temps restant, i només ofereix l'alarma de porta oberta.
33. L'alarma de porta de nevera permet un avís inicial més N repeticions addicionals; tancar la porta rearma l'alarma.
34. Rentadora, rentaplats i assecadora tenen perfils separats encara que comparteixin capacitats. Un perfil futur pot declarar paràmetres i accions diferents sense afegir condicions duplicades a cada capa.
35. Es poden configurar els perfils `mailbox_motion` i `mailbox_slot` amb el seu sensor d'arribada i un contacte separat per a la porta principal.
36. Després d'observar el sensor d'arribada apagat, cada transició a `on` inicia el cicle de bústia, executa les accions comunes d'inici i activa «Pendent de recollir»; l'estat inicial `on` o un estat no disponible no genera una arribada falsa.
37. El cicle de bústia dura mentre hi ha correu pendent. Obrir la porta principal o prémer el botó de buidatge acaba el cicle, executa les accions comunes de final, neteja «Pendent de recollir» i cancel·la recordatoris. Si arriba correu amb la porta oberta, l'estat queda pendent però els recordatoris esperen que la porta es tanqui.
38. La nevera per interruptor (`refrigerator_switch`) exigeix switch i contacte de porta; el switch determina l'activitat del cicle i les accions comunes d'inici/final s'executen quan passa a `on` i `off`. Pot mostrar potència i energia auxiliars i ofereix només l'alarma de porta oberta; ni el switch ni l'endoll opcional de `refrigerator` generen alarmes d'apagat.
39. En editar una entrada existent, el tipus i la modalitat es mostren però no es poden canviar; el nom, les fonts, els paràmetres i les accions es poden editar. Per canviar-los cal crear una entrada nova.
40. En crear o editar un perfil de bústia, el sensor d'arribada i el contacte de la porta principal han de ser entitats diferents; si se selecciona la mateixa entitat, el flux mostra un error i no desa la configuració.
41. El perfil `mailbox_slot` exposa l'estat obert/tancat del sensor de contacte/obertura de portella com una entitat «Portella» separada de «Porta». El perfil `mailbox_motion` no crea aquesta entitat.
42. Tots els perfils que admeten un endoll intel·ligent exposen, quan n'hi ha un de seleccionat, un grup d'accions i paràmetres independents per a l'endoll apagat. El primer avís és immediat, se'n poden configurar N repeticions addicionals, no s'envien repeticions després de `on` i l'estat, recompte i venciment es restauren després d'un reinici.
43. Cada categoria té un pas de modalitat i opcions de traducció propis; cada perfil té identificadors de pas, formularis de sensors, paràmetres i accions, i labels de traducció independents. Les proves han de recórrer totes les categories i perfils i confirmar que els formularis i les claus de traducció estan aïllats, inclosa la indicació explícita «(optional)» o «(opcional)» als camps opcionals.
44. Cada input es representa amb la sortida pròpia del perfil quan n'hi ha; no s'han de crear wrappers visibles per al sensor de pala de l'AC ni per als sensors d'entrada de la bústia. Cada aparell elèctric conserva «En funcionament»; cada bústia conserva «Pendent de recollir» i les sortides «Porta»/«Portella» aplicables.
45. Les proves comproven que només es creen els wrappers declarats pel perfil i que els wrappers obsolets de l'AC i la bústia s'eliminen del registre. Les sortides derivades segueixen les seves fonts; les lectures `unknown`, `unavailable`, la desaparició i la recuperació no han de finalitzar falsament el cicle ni mostrar valors antics com a actuals.
46. Rentadora, rentaplats, assecadora i bústia ofereixen una acció opcional quan es buida la càrrega o es recull el correu. S'executa una sola vegada quan l'estat pendent passa a net per l'obertura de la porta o pel botó de buidatge, i no s'executa si no hi havia res pendent.
47. La jerarquia d'agrupació → classe d'aparell → modalitat/perfil és la mateixa al flux, a `APPLIANCE_GROUPS`, al README i a aquest document; no hi ha arbres contradictoris.
48. Les opcions d'accions de grup mostren la unió ordenada dels hooks suportats per almenys un perfil descendent. Cada appliance només executa hooks del seu perfil quan la capacitat i la font corresponents estan configurades; els hooks globals obsolets o incompatibles no s'executen.
49. Per a cada esdeveniment d'un appliance, les accions globals s'executen abans que les accions locals. La mateixa configuració global executada per dos appliances rep variables pròpies de cadascun; `ham_device_area_name` pot ser `None`, i `ham_source_entity_id` només es passa quan hi ha una entitat d'origen.
50. La unió d'accions de `large_appliances` inclou els hooks de bugaderia i refrigeració, inclosos «pendent de buidar» i «buidat»; cada perfil només executa els hooks que declara. La migració fusiona les llistes de les antigues agrupacions sense perdre cap acció i elimina duplicats.
51. L'aquari es configura a `animal_care` amb `aquarium_plug` o `aquarium_power`, pot exposar les lectures opcionals de lluminositat, temperatura de l'aigua, pH i nivell d'aigua, i no ofereix classes de petits electrodomèstics sense classe definida.
50. La configuració de grup es pot editar sense esborrar-la en editar o retirar un membre. El flux explica visualment, amb ajudes natives localitzades, la jerarquia, la unió de hooks, l'ordre i les variables de plantilla en anglès, castellà i català.

51. Per a qualsevol input visible que el perfil declara representable, una font sense dispositiu pare s'associa directament al dispositiu HAM sense duplicar-la; una font ja assignada conserva el dispositiu i rep un proxy HAM duplicat. Els inputs només interns no tenen entitat visible ni associació directa. Un sensor extern d'energia acumulada sempre rep una còpia proxy amb base de reinici, encara que no tingui pare; l'energia calculada localment no és proxy. Cada còpia té per defecte un nom acabat en ` (HAM Proxy)` i un `entity_id` acabat en `_ham_proxy`; les sortides calculades no porten aquests sufixos. Les fonts mantenen la propietat d'integració i HAM desfà les associacions directes només si encara apunten al seu dispositiu.
## 9. Qualitat i proves

### 9.1 Guia de proves per afegir un perfil o aparell

Abans d'integrar un tipus o perfil nou, cal completar aquesta checklist. Les proves parametritzades existents han de cobrir automàticament el perfil nou quan el seu identificador s'afegeix a `APPLIANCE_PROFILES`; si el perfil introdueix un comportament o una capacitat nova, cal afegir també proves específiques d'aquest comportament.

1. **Registre i contracte del perfil**: comprovar que el perfil apareix exactament una vegada a la categoria/modalitat corresponent, té el nom de model visible i declara correctament les fonts, obligatorietat, domini, capacitats, grups de paràmetres i accions, i entitats de sortida. Executar les proves de `tests/unit/test_config_flow.py`, especialment `test_categories_map_each_profile_to_one_compatible_mode`, `test_device_models_cover_and_distinguish_all_profiles` i `test_each_profile_schema_matches_its_declared_contract`.
2. **Formularis i opcions**: verificar selectors i filtres, camps obligatoris i opcionals, valors per defecte, paràmetres i accions que es mostren només quan pertoquen. Comprovar que editar conserva els valors seleccionats i que treure un sensor opcional elimina el valor desat. Les opcions, els formularis i les traduccions han de correspondre al perfil, sense mostrar camps d'altres perfils.
3. **Traduccions**: afegir les cadenes del perfil a `strings.json` i a les traduccions anglesa, castellana i catalana. Executar les proves de cobertura de claus, etiquetes d'accions i indicació explícita d'obligatorietat/opcionalitat de `tests/unit/test_config_flow.py`.
4. **Cicle CRUD a Home Assistant**: executar `test_every_profile_supports_config_entry_crud` a `tests/component/test_config_flow.py`. Ha de completar la creació, lectura de les dades desades, edició de fonts i opcions, i eliminació de l'entrada per al perfil nou. Si una capacitat opcional es pot afegir o treure durant l'edició, comprovar també que els valors i les entitats dependents s'actualitzen correctament.
5. **Detecció i persistència**: per a una estratègia existent, afegir o ampliar una prova de component que demostri que només la font seleccionada inicia i finalitza l'activitat. Si s'introdueix una estratègia nova, afegir proves unitàries del detector a `tests/unit/test_appliance.py` i proves de component del seu comportament a `tests/component/test_runtime.py`. Cobrir lectures invàlides o no disponibles i restauració després de reiniciar quan siguin aplicables.
6. **Entitats i comportaments declarats**: comprovar a nivell de component que cada input visible segueix la regla universal de no duplicar una font sense pare i duplicar amb proxy una font ja assignada; verificar també que els inputs només interns no es mostren ni es reassignen i que l'energia externa acumulada sempre es duplica per aplicar la base de reinici. Assertar els sufixos de nom i `entity_id` a les còpies, cap sufix a les sortides calculades, propietat original de les fonts, actualització/indisponibilitat, accions reenviades, migració i neteja. Afegir proves específiques per a cada grup nou d'accions, alarma, recordatori o botó, incloent-hi cancel·lació, límits i persistència quan correspongui.
7. **Aïllament i neteja**: verificar que el perfil no altera altres dispositius ni altres modalitats i que, en eliminar l'entrada o retirar una capacitat, es netegen només les entitats pròpies obsoletes; les entitats d'entrada externes de l'usuari es conserven.
8. **Execució final**: executar `pytest -q tests/unit/test_config_flow.py tests/unit/test_appliance.py`, després `pytest -q tests/component/test_config_flow.py tests/component/test_runtime.py` i finalment `pytest -q`. Abans d'integrar o publicar, també han de passar el check de cobertura agregada i la resta de checks obligatoris de CI descrits en aquesta secció.

- La suite ha d'incloure proves unitàries i proves de component de Home Assistant, amb fixtures i dades de prova deterministes. Les proves no han de dependre de dispositius reals ni de serveis externs.
- La cobertura combinada de codi de la integració, calculada a partir de les proves unitàries i de component juntes, ha de ser **com a mínim del 95%**. Un únic check de cobertura agregada ha d'executar o combinar ambdues suites i aplicar `--cov-fail-under=95`; no s'exigeix que cada suite individual assoleixi el 95%. Una cobertura combinada inferior ha de fer fallar el check.
- Les proves han de cobrir com a mínim els passos de creació i edició, cada perfil, fonts i selectors condicionals, estratègies d'activitat, grups d'accions específics, alarmes de nevera, arribades de bústia, entitats condicionals i els casos de cicle, recordatoris, energia i edició.
- Cada perfil ha de tenir proves unitàries dels seus selectors, paràmetres, accions i entitats declarades, i proves de component que completin el cicle CRUD de l'entrada: crear, llegir, editar i eliminar.
- Abans d'integrar canvis a `main` o publicar una versió, tots els checks obligatoris han de passar. Els checks s'han de configurar com a requerits per a les branques protegides de GitHub.

## 10. GitHub Actions i compatibilitat

El repositori ha de tenir workflows independents per als tests unitaris, els tests de component, la validació HACS, la validació Hassfest i la compatibilitat diària:

- **Tests unitaris**: executar la suite unitària i publicar-ne les dades de cobertura per a l'agregador.
- **Tests de component**: executar la integració dins de Home Assistant i publicar-ne les dades de cobertura per a l'agregador.
- **Cobertura agregada**: combinar els resultats unitaris i de component i exigir un mínim del 95% sobre el codi de la integració.
- **Validació HACS**: executar `hacs/action` amb la categoria `integration`.
- **Validació Hassfest**: executar l'acció oficial `home-assistant/actions/hassfest`.
- **Compatibilitat diària**: cada dia a les 06:00 UTC, instal·lar la darrera versió estable disponible de Home Assistant i executar-hi els tests de component. No s'ha de fixar aquesta execució diària a una versió antiga concreta. El workflow també ha de permetre execució manual.
- Els workflows de tests i validació s'han d'executar en `push` a `main`, en `pull_request` cap a `main` i amb `workflow_dispatch`. El workflow diari ha de tenir el disparador `schedule` i `workflow_dispatch`.
- Els errors de validació, tests o cobertura han de deixar el check de GitHub en fallada i impedir la integració o publicació fins que es resolguin.

## 11. GitHub, HACS i publicacions

- El repositori de codi ha de ser públic i tenir documentació d'instal·lació, configuració, entitats, ús, limitacions i suport.
- L'estructura ha de seguir el format d'integració HACS: `custom_components/home_activity_manager/`, manifest vàlid, configuració HACS de categoria `integration`, fitxers de traducció i metadades necessaris per a Home Assistant.
- Abans de cada publicació, han de passar HACS validation, Hassfest, tests i cobertura. El README ha d'incloure badges d'estat dels workflows i de cobertura.
- Les versions han de seguir Semantic Versioning. Els tags Git i els noms de les releases de GitHub han de fer servir el format `vX.Y.Z` (per exemple, `v1.2.3`); la versió numèrica del manifest ha de coincidir amb el tag i la release. Cada release ha d'actualitzar el changelog amb el mateix format.
- La submissió al repositori per defecte de HACS és un pas de publicació separat: preparar-la i demanar-ne la inclusió quan el repositori i la primera release compleixin els requisits de HACS.

## 12. Idiomes i marca

- L'anglès és l'idioma font per a les cadenes de la interfície i la documentació principal del projecte.
- Tots els textos visibles a Home Assistant han de fer servir claus de traducció; no s'han de codificar directament dins la lògica de la integració.
- La interfície ha de tenir traduccions completes en anglès, castellà (`es`) i català (`ca`), inclosos els passos de configuració, tipus, modalitats, noms i estats de les entitats, opcions, validacions i errors.
- Les traduccions han de mantenir el mateix conjunt de claus i significat. Les proves o validacions han de detectar claus absents o sobrants.
- La icona anterior `docs/appliance_cycle_monitor_icon.svg` es conserva com a referència de la marca antiga. Les noves propostes són `docs/home_activity_manager_icon_option_1.svg` (casa i òrbita d'activitat) i `docs/home_activity_manager_icon_option_2.svg` (casa i pols d'activitat); l'usuari n'ha d'escollir una abans d'actualitzar els recursos finals de marca.
- La icona escollida ha de ser llegible a mida petita i sobre fons clars i foscos, i representar activitat domèstica de manera genèrica sense identificar-se només amb un tipus de dispositiu.

## 13. Estat del model i evolució futura

### Tipus generals, modalitats i capacitats

**Estat: implementat a la versió 0.8.0 per als tipus i modalitats actuals.** No s'afegeix, de moment, un tipus de dispositiu personalitzat.

El tipus general, la modalitat que determina l'activitat i les capacitats opcionals són conceptes separats. Els perfils interns fan servir els detectors existents sense perdre les funcions específiques de cada aparell.

El tipus general i la modalitat són fixos després de la creació i han de ser identificables a la interfície. Es pot substituir l'entitat font per una altra compatible amb la mateixa modalitat; una font `climate` no es pot deixar buida en desar, i cal substituir-la o eliminar l'aparell.

La creació segueix cinc passos:

1. **Tipus i nom**: seleccionar el tipus general i donar nom a l'aparell.
2. **Modalitat d'activitat**: triar una modalitat obligatòria entre les compatibles amb el tipus seleccionat.
3. **Fonts i controls**: seleccionar obligatòriament l'entitat corresponent a la modalitat i, opcionalment, les altres fonts i controls compatibles. Si el tipus necessita altres entrades per a una funció concreta, cal definir-ne l'obligatorietat per separat.
4. **Paràmetres**: mostrar només els llindars, temporitzacions i opcions aplicables a les fonts i funcions configurades.
5. **Accions**: mostrar les accions disponibles per a les funcions configurades.

- La modalitat escollida determina quina font mana sobre l'activitat. Els altres sensors poden proporcionar mesures, estats, alarmes o control, però no han d'alterar l'activitat. No s'intenta endevinar si l'usuari ha triat el sensor físic correcte.
- Exemple d'AC: cada modalitat mostra les entrades declarades al seu perfil. El contacte/obertura només és disponible en la modalitat de contacte; potència, energia i interruptor poden coexistir segons la modalitat. Només la font seleccionada determina l'activitat. Una entitat `climate` conserva els controls originals.
- Si la modalitat és l'interruptor, el seu estat determina l'activitat encara que la potència indiqui un altre valor. Si la modalitat és potència, l'interruptor auxiliar no finalitza ni impedeix un cicle.
- En aparells endollats, el control per interruptor, la potència instantània i l'energia acumulada són capacitats independents de la modalitat. L'energia existent es mostra en kWh; si no se selecciona, es calcula a partir de la potència quan n'hi ha. El botó de reinici està disponible quan hi ha potència i reinicia el total de la integració: amb energia externa, fixa una base sense alterar la font i mostra el consum acumulat des d'aquesta base.
- Si la font obligatòria queda `unknown` o `unavailable`, no se substitueix automàticament per una altra ni es provoca una transició falsa. Cada modalitat té una sola font d'activitat seleccionada; no es combinen fonts per decidir l'estat.

### Modalitats i capacitats implementades

| Tipus general | Modalitats actuals que es poden agrupar | Funcions i límits a conservar |
| --- | --- | --- |
| Grans electrodomèstics | Rentadora, assecadora i rentaplats per potència; nevera i congelador per potència o endoll | Cicle i funcions segons cada perfil: bugaderia pot admetre temps màxim, estimació i pendent de buidar; refrigeració admet contacte i alarma de porta. Les accions compartides són la unió dels perfils i es filtren per capacitat. |
| Cura d'animals | Aquari per endoll o potència | Cicle amb lectures opcionals de lluminositat, temperatura de l'aigua, pH i nivell d'aigua; sense pendent de buidar. |
| Aire condicionat | Sensor de contacte/obertura, potència o `climate` | Una sola font d'activitat; el contacte/obertura només existeix en el perfil de contacte. Potència, energia i interruptor es declaren segons cada perfil. La `climate` original conserva associació i controls, sense wrapper. |
| Nevera | Potència o interruptor | Accions d'inici/final d'activitat en totes dues modalitats; contacte i alarma de porta; potència i energia auxiliars són compatibles amb la modalitat d'interruptor. No hi ha alarmes de compressor inactiu o endoll apagat. |
| Bústia | Moviment interior o sensor de contacte/obertura de portella | La modalitat detecta una arribada com a esdeveniment, no un estat de funcionament continu. Cal mantenir la porta principal separada, el pendent de recollir, les accions i els recordatoris. |
| Access | Contacte o cover principal | Estat obert/tancat, durada de l'interval obert i pany opcional; una coberta en moviment no canvia l'últim estat estable. |
| Protecció solar (tendal) | Contacte o cover | Estat/posició obert/tancat i durada; no s'ha de presentar com a funcionament del motor. |

Els detectors i les sortides no són intercanviables: cal conservar la semàntica de cada modalitat. La compatibilitat de dispositius futurs requerirà definir-ne els estats, esdeveniments i controls; també caldrà estudiar si un dispositiu que només agrupa entitats necessita una modalitat d'activitat obligatòria.

### Decisions aplicades

- La potència es mesura independentment de l'activitat. L'energia externa mostra el total original; el total calculat es manté separat. Canviar de font pot canviar el total visible i un sensor extern indisponible no provoca una substitució automàtica.
- Cada tipus declara les modalitats permeses, les entrades obligatòries i opcionals, les capacitats, les alarmes i les accions. En modalitat d'interruptor, aquest determina l'activitat; no hi ha cap alarma separada d'inactivitat del compressor.
- Les configuracions antigues es migren automàticament. Les entrades de rentat i refrigeració es consoliden a `large_appliances` i conserven els identificadors, les opcions locals, les personalitzacions del registre, l'estat runtime i les accions compartides fusionades i deduplicades.
- En substituir la font durant un cicle, se'n conserva l'inici i es finalitza quan la nova font confirma que està aturada; la potència respecta la histèresi i una font indisponible no força una transició. En substituir una `climate`, s'allibera l'anterior sense modificar altres associacions.

### Altres decisions pendents

- Definir límits mínims i màxims dels controls numèrics; els valors inicials sí que queden fixats en aquest document.
- Documentar i revisar les versions mínimes de Home Assistant i Python suportades.
- Investigar l'ampliació de l'abast a dispositius com tendalls i persianes, i a altres dispositius no intel·ligents que es vulguin automatitzar o simplement agrupar sota un únic dispositiu de Home Assistant. Valorar com una sola integració podria reunir-ne diverses funcionalitats i facilitar la descoberta, configuració i ús de les entitats a Home Assistant.

**Data d'actualització**: 2026-10-29