# 007 · Dedup Incremental

**Estado:** implementado ✅

## Qué hace
Evita guardar datos duplicados cuando se scrapea la misma URL con el mismo contenido.

## Requisitos funcionales (EARS)
- CUANDO `save_to_sqlite` recibe un resultado con URL + contenido ya existentes, EL SISTEMA DEBE saltarlo y reportarlo como "saltado por duplicado"
- CUANDO el usuario pasa `--no-incremental`, EL SISTEMA DEBE insertar sin verificar duplicados
- SI la tabla `raw_data` no tiene columna `content_hash`, EL SISTEMA DEBE migrarla automáticamente

## Criterios de aceptación
- [ ] Scrapear la misma URL dos veces → segunda vez saltada por hash
- [ ] `--no-incremental` permite duplicados
- [ ] Test con 2 iguales y 1 diferente → 3 insertos con hash, 2da llamada salta 2
