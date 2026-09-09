To: wen.dai@nuist.edu.cn
Subject: Question on your check-dam detection method — applying it to Spanish river weirs (Guadalquivir basin)

Dear Dr. Dai,

I hope this finds you well. I'm working on a pilot project for Dam Removal
Europe, building a satellite-based pipeline to find undocumented river
barriers (dams and weirs/"azudes") in Spain, starting with the
Guadalquivir basin. No reliable geolocated count currently exists —
registries list somewhere between ~5,000 and ~30,000 recorded structures,
while field-survey extrapolation suggests the real number for Spain could
be over 170,000, with no coordinates behind that gap.

We're building a pipeline that stacks several independent detection
signals — direct image-based structure detection, water-signature
detection, an ecological (algae) confirming signal, and a DEM/hydrological
layer — on the reasoning that no single method catches everything, and
agreement across methods gives higher-confidence detections. Your paper,
"Combining Deep Learning and Hydrological Analysis for Identifying Check
Dam Systems from Remote Sensing Images and DEMs in the Yellow River
Basin," is the best fit we've found for that DEM/hydrological layer — the
reported precision/recall (98.56% / 82.40%) on dam-controlled-area
extraction is notably strong, and specifically targets the kind of small
structures that pure image-detection models tend to miss.

I couldn't find a public code repository for the method, so I wanted to
ask directly:

1. Would you be willing to share any existing code — even
   research-grade/unpublished — for the pipeline? Either the deep-learning
   dam-controlled-area extraction step, the hydrological-analysis
   dam-location step, or both. A private GitHub repo, a Zenodo/OSF
   deposit, or even a shared Drive/Colab folder would all work fine on
   our end.
2. Could you share the parameters the paper doesn't fully specify — DEM
   resolution actually used, the flow-accumulation threshold, OBIA
   segmentation software/settings, and the minimum dam-controlled-area
   size considered? These are the details we'd otherwise have to guess at
   when reproducing the method.
3. Would you be able to share your Jiuyuangou watershed validation data
   (check-dam locations + DEM)? We'd like to benchmark our
   reimplementation against your reported numbers before trusting it on
   new terrain.
4. Most importantly — in your judgment, would this method reasonably
   generalize from Yellow River check dams (small, earthen, silt-trapping
   structures in ephemeral Loess Plateau gullies) to river weirs/azudes on
   a perennial Mediterranean river system like the Guadalquivir? If you
   think the underlying assumptions don't transfer, I'd rather know that
   now than after we've built around it.

If this pilot works, applying your method to a Mediterranean basin for
the first time would itself be a citable result, and we'd of course credit
your work appropriately — happy to discuss what collaboration or citation
would look like if that's of interest.

Thank you for your time, and for the work itself — it's exactly the kind
of method this project needs.

Best regards,
[Your name]
Dam Removal Europe — river-barrier detection pilot
[your email / contact]
