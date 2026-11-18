# Painting knowledge → engine rules

Techniques researched from painting and book-design guides (Nov 15), each turned into a rule the engine follows. Techniques aren't copyrighted. No images were copied, and nothing from Bob Ross's copyrighted paintings is used.

## Mountains and rock
- **See in planes.** Break each mountain into big planes, decide the light direction once, and keep it consistent on every face and every rock. → *slope-based faces, one light direction per scene*
- **Every rock has three planes:** a lit top (brightest, smallest area), a midtone side (the largest area), and a shadow bottom (darkest). No "potato" rocks: angular, flat facets with sharp turns. → *rocks drawn as faceted polygons with three planes*
- **Rock texture comes from hard edges** between values at outcrops; snow and distance soften edges. → *hard-edged outcrop strokes on near rock, soft on far ranges*
- **Atmospheric perspective:** far is lighter, cooler, lower in contrast and less saturated; near is darker and richer. Paint back to front in overlapping layers. → *ranges painted back-to-front with increasing haze*
- **Pointed peaks with sharp, defined edges,** like a palette knife's. → *steeper, pointier summits*

## Sunset skies and clouds
- **At sunset, clouds are lit from below:** warm orange and red undersides, with purplish shadows on their tops. Sunset clouds' own color is dark. → *dark local cloud colour, lit undersides, violet tops*
- **Clouds nearest the horizon catch the light first.**
- **Clouds are 3-D masses that follow perspective,** smaller, flatter and closer together toward the horizon, and as a group they recede toward a vanishing point. → *cloud masses placed in perspective rows, not random noise*
- **Most cloud shapes should touch and connect,** and the negative space (sky showing between them) is designed, not accidental. → *clouds built as connected clusters of billows*
- **Consistent wind:** all clouds trail off in the same direction. → *one wind direction per sky*
- **Contrast is tight in some places and strong at a few points** to direct the eye. → *brightest rims near the sun only*

## Ground and grass
- **The foreground has the most detail and contrast;** the distance is simplified, softer and cooler.
- **Grass is a mix of blades, clumps and varying lengths.** Don't paint every blade. Layer dark accents (shadow), then colour, then a few bright flicks of highlight last. → *clumped grass, power-law lengths, three-layer strokes*
- **Each clump's shadow follows the contour of the land.**
- **Warm light, cool shadows.** → *shadows tinted violet/blue in sunset scenes, not just darkened*

## Shadows
- **The vocabulary:** light side, highlight, halftone, core shadow, reflected light, and a cast shadow with a hard edge near the object that softens with distance. → *cast shadows hard at the contact point, softening away*

## Book layout and type
- **Captions:** set smaller than body text with tighter leading, and centered when shorter than one line. Leave a consistent gap between image and caption.
- **Margins:** inside (gutter) ¾"–1", other margins at least ½". **Never put a header or footer on blank pages or chapter openings.** Running heads are smaller than the body, often in small caps.
- **Fonts:** use the same 2–3 typefaces throughout, and keep chapter-title and subhead styling consistent. Body text is usually 10–12 pt.
- **Images** print at **300 DPI** at their printed size and are placed **next to or just after** what they illustrate.
- **On painted pages** (the engine's caption placement): no bar; the darkest, calmest band clear of the subject; a soft glow behind the text; safe margins; balanced line breaks.

## Still to research and build (for the app)
Brush types and how to simulate them (charcoal, ink, marker, crayon, palette knife, dry brush, glazing), plus cover, logo, ad and thumbnail layout standards.

---
## From *Introduction to Digital Art* (K. R. Kennedy, College of Lemoore, CC BY-SA 4.0)
Summarized in our own words. The source is an open textbook supplied by the author.

**Elements of art:** line, shape and form, color, texture, space (positive and negative) and value. Value carries depth and highlights. → *the engine builds every scene on a value plan first: dark foreground, lit mid-ground, glowing sky*

**Principles of design:**
- **Balance:** symmetric, asymmetric or radial; no part overpowers the rest.
- **Contrast** directs attention. **Emphasis** puts the focal point first, through color, contrast, size and placement.
- **Movement** leads the eye to the focal point. **Pattern and rhythm** come from repetition. **Unity** comes from a shared palette and brushwork.

**Composition techniques:**
- **Rule of thirds:** key elements on the third lines or their crossings. → *figures and sun near a thirds line*
- **Leading lines** toward the subject: ridgelines, paths, rivers. **Framing** with natural elements → *clouds framing the sky window*
- **Scale and proportion:** bigger reads as more important or nearer. **Asymmetry** for dynamic tension → *the figures' asymmetry*
- **Depth** through atmospheric perspective (color and clarity fade with distance), layering, and soft-versus-sharp focus.

**Visual hierarchy:** size and scale, contrast, color, placement, whitespace, repetition and alignment. The viewer reads the most important thing first. → *caption placement: the subject is never covered; text sits in calm negative space*

**Gestalt:** figure-ground separation (subjects read against the background), similarity, proximity, closure and continuity. → *silhouettes must separate cleanly from the ground (rim light, value contrast)*

**Color:**
- **Harmonies:** analogous (calm), complementary (strong contrast; the book's example is orange against blue in a sunset) and triadic (vibrant).
- **Temperature:** warm colors advance and energize; cool colors calm and recede.
- **Value** is lightness, and **saturation** is intensity: a saturated subject pops against a muted background.
→ *sunset scenes pair hot orange lights with cool blue-lavender gaps and violet shadows*

**Brush model** (for the app's brushes):
- **Shape and size:** tip shape, size and **hardness** (soft or hard edge).
- **Laying paint down:** **spacing** (smooth or dotted), **opacity**, and **flow** (build-up rate).
- **Variation:** **shape dynamics** (size and angle jitter), **scattering**, **texture**, **dual brush** and **color dynamics** (hue and brightness jitter).
- **Smoothing,** and **blend modes:** multiply darkens, screen lightens, overlay does both.
→ *the engine's soft brush already has opacity, round tips and color jitter; hardness, spacing, scattering and blend modes are next*

---
## From *Digital Painting Techniques: Practical Techniques of Digital Art Masters* (3DTotal / Focal Press, 2009)
A copyrighted book supplied by the author for study. These are technique notes in our own words only. No text or images from the book are reproduced or stored here.

**Speed-painting process:**
1. Block the whole composition in **black and white** first, then grays, then put **color on a separate layer last**.
2. Work zoomed out on overall harmony before any detail.
3. **Dark values near the focal point** pull the eye there.
4. Fill empty areas with small story details only if the composition needs them. → *engine order: value plan, then forms, then colour; the darkest darks and strongest contrast sit by the figures*

**Depth (from matte painting):**
- **Near:** full color range and full contrast.
- **Middle:** contrast starts to drop.
- **Far:** only **two shades** (a highlight and a shadow), both shifted toward the sky's color, with **low contrast, high brightness and low saturation**.
- **Haze** is painted more over distant elements and less over near ones.
- **Scale** must stay consistent with neighboring objects. Scale errors are the most common realism mistake.
→ *far ranges posterised to two sky-tinted shades*

**Brushes:**
- Professionals use **very few brushes** (often two or three standard ones) and keep custom brushes for textures and backgrounds.
- **A custom tip** starts from **irregular, never symmetrical** shapes, with a **high-contrast grayscale texture** overlaid on them. Then the settings add jitter (size, angle, scatter, dual brush, texture) to hide repetition.
→ *app roadmap: a "make a brush from an image" feature*

**Water** (a calm sea):
- **The sea reflects the sky above it.** Start with a muted base, then lay **broken horizontal light marks** in layers at different strengths.
- Put **stronger, brighter marks in a column under the sun**.
- Rough marks are fine early on and get refined later.
→ *for the sea and Atlantis scenes*

---
## Brush types (researched: the Krita manual's brush engines, art-supply brush-shape guides)
The app's brush engine (`brushes.py`, 45 brushes, see `brush_sampler.png`) covers four groups.

**Traditional shapes:**
- **Round:** the most versatile; detail and lines.
- **Flat:** broad, even coverage. **Bright:** a short, stiff flat, for impasto and bold strokes.
- **Filbert:** a flat with a domed tip; coverage plus soft edges and rounded shapes.
- **Fan:** blending, feathery textures, grass, fur and foliage.
- **Angular:** cuts into corners. **Dagger:** a long angled tip, for one-stroke leaves.
- **Liner/rigger and script:** long, fine continuous lines, branches and rigging.
- **Mop:** soft, full, for glazes and blending. **Spotter:** tiny precise detail.
- **Palette knife:** sharp-edged, scraped paint.

**Dry media:** pencil, charcoal, pastel/chalk and crayon, all grain-dependent on the paper texture; ink pen (tapered), calligraphy (a fixed-angle nib) and marker (translucent layers that build up).

**Wet media:**
- **Watercolor:** transparent, pooling darker at its edges.
- **Oil:** bristle marks, with impasto highlights.
- **Gouache:** matte and opaque. **Acrylic:** opaque, quick.
- **Also:** airbrush, dry brush, sponge and splatter.

**Krita-style engines:** bristle, spray, particle, sketch, hatching, curve, grid, shape, smudge/blender, blur (filter), deform/push, clone, glaze (multiply), glow (screen), eraser. **Plus subject brushes:** grass blades, foliage and stipple.

**Shared settings** (from the textbook's brush model): size, spacing, flow and opacity, hardness, size and angle jitter, scatter, color jitter, paper grain, pressure taper and blend mode (normal, multiply, screen, erase).

---
## Art styles (styles_fx.py): how each look is made
- **Painterly** is the engine's own brushwork (the default). **Realism** adds refined detail with fine and broad sharpening, and natural color.
- **Oil Painting, Watercolor, Pastel and Pencil Sketch** use the brush engine (img2img mediums).
- **Black and White** is a red-filter monochrome (dramatic skies), with a contrast curve and fine grain.
- **Cartoon:** smoothed, flat colors (14) and bold outlines. **Anime:** cel shading in three light bands per color, vivid, with thin lines; the deepest shadows stay dark so silhouettes survive.
- **Comic Book:** flat colors, halftone dots in the shadows, ink outlines. **Pop Art:** a 6-color pop palette mapped by light level, Ben-Day dots and thick outlines.
- **Street Art:** a stencil mural. Saturated poster colors on the darker shapes, bare concrete wall in the light areas, a spray halo, drips and thick outlines.
- **Pixel Art:** box-downsampled to chunky pixels, with a 24-color palette.
- **Abstract:** color fields (Voronoi cells), translucent shapes and gestural lines.
- **Impressionist:** bright, saturated, short broken dabs in two passes over a soft underpainting.
- **Stained Glass:** glowing saturated panes and dark lead lines. **Woodblock Print:** flat muted colors, navy outlines, wood grain and paper.
- **Neon:** glowing edge lines in a magenta-to-blue gradient on near-black. **Low Poly:** Delaunay triangles seeded on edges, filled with sampled color.
- **Gallery previews render at a real size, then shrink,** because outline and dot sizes scale with the picture.
