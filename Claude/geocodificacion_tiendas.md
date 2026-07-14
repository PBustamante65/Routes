# Geocodificación de tiendas — resumen

## Objetivo
Obtener latitud/longitud de las tiendas en `RutaEditado.xlsx` (originalmente `.numbers`, convertido a Excel) para trabajarlas en Python/Pandas.

## Archivos
- **Fuente**: `Data/RutaEditado.xlsx`, hoja `RELACION TIENDAS`. El header real está en la fila 3 del excel (`header=2` en pandas); columnas: `tienda`, `direccion` (incluye ciudad como texto libre), `ciudad`, `costo_mensual`.
- **Salida**: `Data/RutaEditado_coordenadas.xlsx`, con columnas agregadas `direccion_geocodificar`, `direccion_aproximada`, `latitud`, `longitud`.
- **Pipeline**: `Code/geocode.py` — `python3 geocode.py` (primera pasada) y `python3 geocode.py --retry` (reintenta filas sin coordenadas).

## Problemas de datos encontrados en el excel original
- 9 filas totalmente vacías (separadores) — se descartan con `dropna(subset=["tienda"])`.
- 12 tiendas con ciudad pero sin dirección de calle (8 en Chihuahua + 4 en Saucillo: VIA LIBRE, EL SAUCILLO, LAS VARAS, GUERRERO). Para estas se geocodifica `"{tienda}, {ciudad}, MEXICO"` en vez de la dirección completa (columna `direccion_aproximada = True` marca estas filas).
- Algunas celdas de dirección/ciudad quedaron corrompidas como fechas de Excel (ej. tienda VALLE ESCONDIDO con dirección `2014-06-21 00:00:00`, tienda TOPACIO con ciudad `2014-07-29 00:00:00`). Pendiente de corregir a mano en el excel fuente si se quiere recuperar esas coordenadas.

## Método de geocodificación
- Librería `geopy` con `Nominatim` (OpenStreetMap, gratis, sin API key).
- Gotcha importante: el timeout default de geopy es de 1 segundo, insuficiente para el servidor público de Nominatim — causaba falsos timeouts en la primera corrida. Se corrigió con `timeout=10` (y `timeout=15` en el reintento).
- Nominatim aplica rate limiting (429) si detecta ráfagas de requests, incluso respetando 1 req/seg. El reintento usó `min_delay_seconds=2.5` para bajar la tasa de 429.

## Resultado final
- **87 de 223 tiendas (39%) con coordenadas.**
- **136 sin coordenadas** — mayoritariamente porque Nominatim/OpenStreetMap no tiene buena cobertura de direcciones informales mexicanas (ej. "AV. X NO. 123 ESQ. CON CALLE Y", fraccionamientos sin geocodificar), no solo por rate limiting.
- Se decidió dejar el resultado parcial tal cual, sin seguir reintentando ni migrar a Google Maps Geocoding API por ahora.

## Próximos pasos posibles (si se retoma)
1. Corregir a mano las direcciones corruptas (fechas de Excel) y las direcciones ambiguas antes de reintentar.
2. Evaluar Google Maps Geocoding API para las 136 pendientes — mejor manejo de direcciones informales, pero requiere API key y tiene costo pasado el crédito gratuito.
3. Filtrar pendientes en Pandas con `df[df["latitud"].isna()]` sobre `RutaEditado_coordenadas.xlsx`.
