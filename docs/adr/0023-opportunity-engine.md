# ADR-0023 — Content Opportunity Engine : critères mesurés seulement, demande FR observée exigée

- Statut : Accepté
- Date : 2026-11-15

## Décision

1. **Signaux croisés en lecture seule** depuis les modules existants :
   - écart EN→FR (phase 8) ;
   - vues FR mesurées et canaux concurrents ;
   - demandes, questions et contestations de la communauté (phase 15) ;
   - segments liés au sujet ;
   - pages transcrites pertinentes : plein texte uniquement, la similarité vectorielle seule
     ne compte pas comme preuve ;
   - théories non réfutées (phase 7).
2. **Score `opportunity@1`** :
   - moyenne pondérée des **seules** composantes mesurées ;
   - poids : écart 0,25, demande FR 0,20, documentation 0,20, communauté 0,15,
     originalité 0,10, audience 0,10 ;
   - confiance = part du poids mesuré (HIGH ≥ 0,75, MEDIUM ≥ 0,5, sinon LOW) ;
   - les critères non mesurés sont listés.
3. **Popularité anglophone ≠ demande francophone** : sans vues FR mesurées ni demande de la
   communauté, un sujet reste une **HYPOTHESIS**, jamais « PRIORISER ».
4. **Fiche par sujet** : public potentiel, besoin, angle, preuves, concurrence, risques,
   formats (selon les niveaux de connaissance des segments), recommandation, confiance.
5. La compatibilité avec l'identité Primestone viendra avec la charte et les séries
   (phase 18).

## Conséquences

- Le moteur ne recommande rien de fort sans données ; il dit ce qui manque pour conclure.
