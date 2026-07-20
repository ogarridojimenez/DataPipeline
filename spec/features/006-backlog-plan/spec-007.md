# 007 · Dedup Incremental

## Qué hace
Evita re-scrapear URLs ya procesadas. Cuando el contenido no ha cambiado, se salta sin duplicar.

## Requisitos funcionales (EARS)
- CUANDO `scrape` se ejecuta con `--incremental`, EL SISTEMA DEBE calcular un hash del contenido y evitar insertar duplicados
- MIENTRAS el mismo contenido ya existe en `raw_data`, EL SISTEMA DEBE saltar la inserción y reportarlo
- SI `--incremental` está desactivado (`--no-incremental`), EL SISTEMA DEBE insertar siempre (comportamiento anterior)
- CUANDO se detectan duplicados, EL SISTEMA DEBE mostrar cuántos se saltaron

## Criterios de aceptación
- [ ] Scrapear 2 veces la misma URL con `--incremental` solo inserta la primera vez
- [ ] Scrapear URLs diferentes siempre inserta aunque sean del mismo dominio
- [ ] Sin flag, incremental está activo por defecto
- [ ] Test: verificar que la segunda ejecución salta duplicados
