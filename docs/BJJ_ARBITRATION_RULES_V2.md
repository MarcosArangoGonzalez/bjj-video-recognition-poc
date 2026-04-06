# Reglas de Arbitraje BJJ v2

1. Jerarquía de Sumisión (Solo 1 por bloque):
   - TRIANGLE > ARMBAR > KIMURA > AMERICANA.
   - Si Triangle tiene > 0.60, ignora el resto.

2. Anclaje Posicional (Inercia):
   - Si la posición previa era MOUNT y la actual es 50/50 con confianza < 0.85, mantener MOUNT.
   - La posición solo cambia si se mantiene estable durante 10 frames consecutivos.

3. Filtro de Ruido:
   - No reportar ninguna técnica con confianza < 0.65.
   - Es mejor "No Data" que "Información Falsa".
