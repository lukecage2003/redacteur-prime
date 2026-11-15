# ADR-0026 — Content Performance Lab et critères de complétude

- Statut : Accepté
- Date : 2026-11-15

## Décision

1. **Boucle** RESEARCH → STRATEGY → SCRIPT → PRODUCTION → PUBLISH → MEASURE → DIAGNOSE →
   LEARN → OPTIMIZE, suivie par sujet (script) à partir des données réelles : chaque étape est
   faite ou non, et la prochaine étape est indiquée.
2. **Modules** (`perf-lab@1`) :
   - **Video Autopsy** : constats classés OBSERVED (décrochages réels, questions du
     public), HYPOTHESIS (repères du script, critères faibles) et DEMONSTRATED (expériences
     concluantes) ; ce qui manque pour conclure est listé ;
   - **Hook Laboratory** : type d'accroche face à la rétention des 10 premiers % ; INSUFFISANT
     sous 3 vidéos ; une expérience HOOK est exigée pour conclure ;
   - **Audience Drop-off** : décrochages observés, agrégés par section ;
   - **Returning Audience** : spectateurs connus / uniques par objectif, NON FOURNI sans les
     deux métriques ;
   - **Packaging et Creative Experimentation** : via les expériences (phase 14) et les tests
     proposés (phase 18).
3. **Validation de l'extension** : les 13 critères sont évalués **sur les données en base**.
   - Un critère est DEMONSTRATED dès qu'au moins une preuve réelle existe ; sinon NOT YET,
     avec ce qui manque.
   - La plateforme n'est déclarée complète que si les 13 critères sont démontrés.
4. **Mission** `VIDEO_AUTOPSY` (Performance Analyst).

## Conséquences

- La complétude se constate, elle ne se déclare pas : en l'absence de données réelles (base
  vide), le rapport affiche 0/13.
