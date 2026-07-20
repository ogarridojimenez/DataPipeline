# 006 · Multi-target Scraping

**Estado:** implementado ✅

## Qué hace
Limita el número de requests simultáneos al scrapear múltiples URLs. Evita saturar el servidor objetivo o la conexión local.

## Requisitos funcionales (EARS)
- CUANDO el usuario ejecuta `scrape` con `--concurrency N`, EL SISTEMA DEBE limitar a N requests simultáneos como máximo
- MIENTRAS el número de URLs supera la concurrencia máxima, EL SISTEMA DEBE encolar las restantes y procesarlas cuando haya slots libres
- SI `--concurrency` no se especifica, EL SISTEMA DEBE usar un valor por defecto (10)

## Criterios de aceptación
- [ ] `--concurrency=1` procesa URLs una a una (serial)
- [ ] `--concurrency=5` procesa hasta 5 URLs en paralelo
- [ ] Sin flag, usa 10 como default
- [ ] Test: verificar que no se supera el límite de concurrencia
