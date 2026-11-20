"""
studio_groups.py: layer groups for the Draw studio.

A group is a folder of layers that sit together in the stack. In the layer list its row shows above its layers: the ball shows /
hides the whole group, the arrow folds it open / shut, and clicking the row selects the group (then Blend and Opacity are the
group's, the arrows move the whole group, Merge flattens it into one layer and Delete removes it with its layers). A group is
painted as one picture first (its layers together), then laid on what's below with its own opacity and blend mode.

Layers keep their group as L.group (an id in self.groups, or None); the layers of a group are always next to each other.
Mixed into DrawStudio (draw_studio.py).
"""
import numpy as np
import theme as T

class Group:
    def __init__(self, name):
        self.name = name; self.visible = True; self.opacity = 1.0; self.mode = "normal"; self.collapsed = False

class StudioGroups:
    def _groups_init(self):
        if not hasattr(self, "groups"): self.groups = {}; self.sel_group = None; self._gid = 0

    def _group_of(self, L):
        g = getattr(L, "group", None)
        return g if g is not None and g in getattr(self, "groups", {}) else None

    # ------------------------------------------------------------------ painting a stack of layers (with groups) into a picture
    def _blend_one(self, part, L, sl, base_al):
        """one layer onto part (clipping to the layer below's coverage if it's clipped); returns (part, coverage for clipping)"""
        from draw_studio import blend_layer
        if getattr(L, "clip", False):
            if L.visible: part = blend_layer(part, L, sl, clip=base_al if base_al is not None else np.zeros(part.shape[:2], np.float32))
            return part, base_al
        base_al = L.shown(sl) * L.opacity if L.visible else np.zeros(part.shape[:2], np.float32)
        if L.visible: part = blend_layer(part, L, sl)
        return part, base_al

    def _runs(self, layers):
        """the stack bottom to top as runs: (group id or None, [layers])"""
        out = []
        for L in layers:
            g = self._group_of(L)
            if g is not None and out and out[-1][0] == g: out[-1][1].append(L)
            else: out.append((g, [L]))
        return out

    def _group_picture(self, members, sl, shape):
        """a group's layers together, on nothing: (colour, coverage)"""
        import brushes
        col = np.zeros(shape[:2] + (3,), np.float32); al = np.zeros(shape[:2], np.float32); base_al = None
        for L in members:
            if getattr(L, "clip", False):
                if not L.visible: continue
                a = L.shown(sl) * L.opacity * (base_al if base_al is not None else 0)
            else:
                base_al = L.shown(sl) * L.opacity if L.visible else np.zeros(shape[:2], np.float32)
                if not L.visible: continue
                a = L.shown(sl) * L.opacity
            src = L.img.a[sl]
            top = src if L.mode == "normal" else np.where(al[..., None] > 0.002, brushes.blend_rgb(col, src, L.mode), src)
            out = a + al * (1 - a); col = (top * a[..., None] + col * (al * (1 - a))[..., None]) / np.maximum(out, 1e-5)[..., None]; al = out
        return col, al

    def _composite(self, part, sl):
        """every visible layer and group over part (the background in that region)"""
        import brushes
        base_al = None
        for g, members in self._runs(self.layers):
            if g is None:
                for L in members: part, base_al = self._blend_one(part, L, sl, base_al)
                continue
            G = self.groups[g]
            if not G.visible: base_al = np.zeros(part.shape[:2], np.float32); continue
            col, al = self._group_picture(members, sl, part.shape); a = (al * G.opacity)[..., None]
            c = col if G.mode == "normal" else brushes.blend_rgb(part, col, G.mode)
            part = part * (1 - a) + c * a; base_al = al * G.opacity
        return part

    # ------------------------------------------------------------------ the rows of the layer list
    def _row_items(self):
        """top to bottom: ("g", group id) for a group's row, ("l", layer index) for a layer's (folded groups hide their layers)"""
        self._groups_init(); items = []; prev = None
        for i in range(len(self.layers) - 1, -1, -1):
            g = self._group_of(self.layers[i])
            if g is not None and g != prev: items.append(("g", g))
            prev = g
            if g is not None and self.groups[g].collapsed: continue
            items.append(("l", i))
        return items

    def _tidy_groups(self):
        """a group's layers stay together: a layer cut off from its group leaves it; a layer dropped between two of a group's
        layers joins; empty groups go"""
        self._groups_init(); L_ = self.layers
        for i, L in enumerate(L_):                                                   # dropped between two layers of one group: it's in
            if self._group_of(L) is None and 0 < i < len(L_) - 1:
                a, b = self._group_of(L_[i - 1]), self._group_of(L_[i + 1])
                if a is not None and a == b: L.group = a
        seen = {}
        for g, members in self._runs(L_):                                            # a group in two places: the bigger part keeps it
            if g is None: continue
            if g in seen:
                small = members if len(members) <= len(seen[g]) else seen[g]
                for L in small: L.group = None
                if small is seen[g]: seen[g] = members
            else: seen[g] = members
        used = {self._group_of(L) for L in L_}
        for g in list(self.groups):
            if g not in used: del self.groups[g]
        if self.sel_group not in self.groups: self.sel_group = None

    # ------------------------------------------------------------------ group actions
    def group_layers(self):
        """Group: this layer and the one under it into a group (or into the group next to it)"""
        self._groups_init()
        if self.sel_group is not None: T.banner(self.app, "THAT'S ALREADY A GROUP — pick a layer to group it with the one below"); return
        if self.li == 0: T.banner(self.app, "NOTHING BELOW — a group needs this layer and the one under it"); return
        cur, below = self.layers[self.li], self.layers[self.li - 1]; gc, gb = self._group_of(cur), self._group_of(below)
        if gc is not None and gc == gb: return
        if gb is not None and gc is None: cur.group = gb
        elif gc is not None and gb is None: below.group = gc
        else:
            if gc is not None:                                                       # two groups side by side: the lower one takes this layer
                cur.group = gb
            else:
                self._gid += 1; g = self._gid; self.groups[g] = Group(f"Group {len(self.groups) + 1}"); cur.group = below.group = g
        self._tidy_groups(); self._after_groups()

    def ungroup(self):
        self._groups_init(); g = self.sel_group if self.sel_group is not None else self._group_of(self.cur)
        if g is None: return
        for L in self.layers:
            if self._group_of(L) == g: L.group = None
        del self.groups[g]; self.sel_group = None; self._after_groups()

    def select_group(self, g):
        self.sel_group = g; idx = [i for i, L in enumerate(self.layers) if self._group_of(L) == g]
        if idx: self.li = idx[-1]                                                     # painting goes onto its top layer
        self._layers_ui()

    def toggle_group(self, g, what):
        G = self.groups[g]
        if what == "visible": G.visible = not G.visible; self._picture_changed()
        else: G.collapsed = not G.collapsed
        self._layers_ui()

    def move_group(self, d):
        """the whole group up / down past the layer (or group) next to it"""
        g = self.sel_group; idx = [i for i, L in enumerate(self.layers) if self._group_of(L) == g]
        if not idx: return
        lo, hi = idx[0], idx[-1]; block = self.layers[lo:hi + 1]; rest = self.layers[:lo] + self.layers[hi + 1:]
        runs = self._runs(rest); pos = 0; k = 0                                      # where the block sits among the other runs
        for k, (gg, mem) in enumerate(runs):
            if pos >= lo: break
            pos += len(mem)
        else: k = len(runs)
        k = max(0, min(len(runs), k + d)); flat = [L for _, mem in runs[:k] for L in mem]
        self.layers = flat + block + [L for _, mem in runs[k:] for L in mem]
        self.li = self.layers.index(block[-1]); self.undo_stack.clear(); self._after_groups()

    def delete_group(self):
        g = self.sel_group
        keep = [L for L in self.layers if self._group_of(L) != g]
        if not keep:
            from draw_studio import Layer
            w, h = self.size_wh; keep = [Layer(w, h, "Layer 1")]
        self.layers = keep; del self.groups[g]; self.sel_group = None; self.li = min(self.li, len(self.layers) - 1)
        self.undo_stack.clear(); self._after_groups()

    def merge_group(self):
        """flatten the group into one layer (what you see stays the same)"""
        from draw_studio import Layer
        g = self.sel_group; idx = [i for i, L in enumerate(self.layers) if self._group_of(L) == g]
        if not idx: return
        G = self.groups[g]; w, h = self.size_wh; sl = (slice(None), slice(None))
        col, al = self._group_picture(self.layers[idx[0]:idx[-1] + 1], sl, (h, w))
        L = Layer(w, h, G.name); L.img.a = col; L.img.alpha = al; L.opacity = G.opacity; L.mode = G.mode; L.visible = G.visible
        self.layers = self.layers[:idx[0]] + [L] + self.layers[idx[-1] + 1:]; del self.groups[g]; self.sel_group = None
        self.li = idx[0]; self.undo_stack.clear(); self._after_groups()

    def _after_groups(self):
        self._layers_ui(); self._picture_changed()

    def _stack_clear(self):
        """every layer and group with no background (for saving see-through): (colour, coverage)"""
        import brushes
        w, h = self.size_wh; sl = (slice(None), slice(None)); col = np.zeros((h, w, 3), np.float32); al = np.zeros((h, w), np.float32)
        for g, members in self._runs(self.layers):
            if g is None: c_, a_ = self._group_picture(members, sl, (h, w)); mode = "normal"; op = 1.0; vis = True
            else: G = self.groups[g]; c_, a_ = self._group_picture(members, sl, (h, w)); mode, op, vis = G.mode, G.opacity, G.visible
            if not vis: continue
            a = a_ * op; top = c_ if mode == "normal" else np.where(al[..., None] > 0.002, brushes.blend_rgb(col, c_, mode), c_)
            out = a + al * (1 - a); col = (top * a[..., None] + col * (al * (1 - a))[..., None]) / np.maximum(out, 1e-5)[..., None]; al = out
        return col, al
