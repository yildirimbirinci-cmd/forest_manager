# Stage 5D.9 - Cluster Apply Plan Preview

Purpose:
prepare the Forest Pack Clusters mode transition without modifying the scene.

Verified live property mapping:
- divers = Diversity mode
- clusize = Cluster Size
- clurough = Roughness
- clunoise = Noise
- cluedge = Blurry Edge

External verification:
- iToo Forest Pack documentation states that Clusters uses Size, Roughness,
  Blurry Edge, and Noise.
- An iToo forum Forest preset example stores `divers=2` together with those
  cluster parameters, supporting the mapping `2 = Clusters`.

Stage 5D.9 is read-only.

The proposed apply changes only:

    divers: 0 -> 2

It preserves the currently observed cluster parameter values and all protected
Forest Manager state, including 75.0 m density, current geometry probabilities,
native scale variation, rotation disabled, and translation disabled.
