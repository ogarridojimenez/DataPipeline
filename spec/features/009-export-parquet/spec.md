# 009 · Export Parquet

**Estado:** implementado ✅

## Objetivo
Exportar datos procesados en formato columnar Parquet.

## RF (EARS)
- CUANDO `--format parquet` en CLI `export`, EL SISTEMA DEBE generar `.parquet`
- CUANDO no hay datos, EL SISTEMA DEBE advertir sin crash
