#target illustrator
/*
 * 甜品菜单排版脚本（Adobe Illustrator）
 *
 * 用法：Illustrator → 文件 → 脚本 → 其他脚本…（Ctrl/Cmd + F12）→ 选择本文件
 *   1. 先弹窗选产品图：选 AI 生成的整页图（上方约 50% 留空给文字）；点“取消”则先放占位框
 *   2. 自动新建 A4、CMYK、3mm 出血的文档，按图层排好 背景 / 产品图 / 装饰 / 文字
 *   3. 完成后 文件 → 存储为… → Adobe Illustrator (*.AI)
 *
 * 菜单文字、颜色、尺寸都在下面的 CONFIG 里改。
 * 本文件是 UTF-8 编码，用记事本等工具修改后请仍以 UTF-8 保存，否则中文会乱码。
 */
(function () {

    // ======================= 可修改区域 =======================

    var CONFIG = {
        pageWidth: 210,     // 成品尺寸（mm），A4 = 210 × 297
        pageHeight: 297,
        bleed: 3,           // 出血（mm）

        // 产品图铺法："full"   = 整页铺满（推荐：AI 出整张场景，上方约 50% 留空给文字）
        //            "bottom" = 只铺下半部分，从 imageTop 铺到页面底部
        imageMode: "full",
        imageTop: 150,      // 产品图区域上边缘距页面顶部（mm）；没选图时占位框也从这里开始
        embedImage: true,   // true = 图片嵌入 .ai 文件，发给客户不会丢图

        goldAsSpot: false,  // true = 金色设为专色“烫金”，方便印刷厂单独出烫金版

        // 颜色（CMYK，0–100），生成后在色板里改一处，全文跟着变
        colors: {
            dark: [55, 75, 85, 70],     // 深咖背景
            glow: [30, 60, 75, 20],     // 背景光晕
            gold: [15, 32, 48, 0],      // 香槟金
            cream: [3, 7, 14, 0]        // 米白文字
        },

        title: {
            badge: "悦",                // 圆形金底里的字
            main: "飨甜馔",
            bigIndex: 1,                // main 里放大的那个字（从 0 数起）：1 = “甜”；不放大填 -1
            en: "CAKE\rSELECTION"       // \r 表示换行
        },

        // 菜品；unit 有值时先出一行规格表头（份 Piece / 磅 Pound），descCn / descEn 可省略
        items: [
            { unit: "份 Piece", cn: "海盐芝士蛋糕", en: "Sea Salt Cheese Cake", price: "¥48" },
            { cn: "剧院蛋糕", en: "Opera Cake", price: "¥48" },
            {
                unit: "磅 Pound", cn: "每日精选蛋糕", en: "Daily Special Cake", price: "¥168",
                descCn: "每日口味随机供应：开心果巴斯克蛋糕 / 巧克力蛋糕 / 老上海蛋糕",
                descEn: "Flavor served daily at random: Pistachio Basque Cake / Chocolate Cake / Old Shanghai Style Cake"
            }
        ],

        noteCn: "*如需选定心仪款式的蛋糕，敬请您提前一天预约",
        noteEn: "Please place your order one day in advance for specific flavor requests",

        logoText: "LOGO"    // Logo 占位，之后换成客户的 Logo
    };

    // 字体候选（PostScript 名），按顺序使用第一个已安装的
    var FONTS = {
        cnTitle: ["SourceHanSerifSC-Heavy", "SourceHanSerifCN-Heavy", "NotoSerifCJKsc-Black", "NotoSerifSC-Black",
            "SourceHanSerifSC-Bold", "SourceHanSerifCN-Bold", "NotoSerifCJKsc-Bold", "NotoSerifSC-Bold",
            "STSongti-SC-Black", "STSongti-SC-Bold", "STZhongsong", "AdobeSongStd-Light", "SimSun"],
        cnBody: ["SourceHanSerifSC-Regular", "SourceHanSerifCN-Regular", "NotoSerifCJKsc-Regular", "NotoSerifSC-Regular",
            "STSongti-SC-Regular", "STSong", "AdobeSongStd-Light", "SimSun"],
        enTitle: ["Cinzel-Regular", "TrajanPro3-Regular", "TrajanPro-Regular", "MinionPro-Regular", "TimesNewRomanPSMT"],
        enBody: ["EBGaramond-Regular", "EBGaramond12-Regular", "AGaramondPro-Regular", "MinionPro-Regular", "TimesNewRomanPSMT"]
    };

    // 版式（mm，从成品左上角算起），字号单位为 pt
    var L = {
        left: 20.5,                                     // 左右边距
        priceX: 179,                                    // 价格列中心
        glowX: 105, glowY: 175, glowD: 300,             // 背景光晕圆心与直径
        placeholderBottom: 278,                         // 占位框下边缘
        badgeX: 29.5, badgeY: 27, badgeD: 18, badgeSize: 36,
        mainX: 40, mainBase: 34, mainSize: 44, mainBigSize: 62,
        enX: 101.5, enBase: 24.5, enSize: 20, enLeading: 9,
        listTop: 48,                                    // 第一行的基线
        unitToName: 10.5, nameToEn: 7, itemGap: 13.5, enToUnit: 11,
        enToDesc: 8, descLine: 5.5, toNote: 9, noteLine: 5,
        unitSize: 15, nameSize: 17, enNameSize: 16, priceSize: 15,
        descSize: 10, descEnSize: 9.5, noteSize: 8.5, noteEnSize: 9,
        logoBase: 284, logoSize: 20
    };

    // ======================= 以下一般不用改 =======================

    var MM = 72 / 25.4;
    var FONT_LABELS = { cnTitle: "中文标题", cnBody: "中文正文", enTitle: "英文标题", enBody: "英文正文" };
    var doc, ox, oy;
    var C = {}, F = {}, fontReport = [], warnings = [];

    function mm(v) { return v * MM; }
    function X(v) { return ox + mm(v); }
    function Y(v) { return oy - mm(v); }

    function main() {
        var imgFile = File.openDialog("选择产品图（AI 生成的整页图，上方留空给文字）。点“取消”则先放占位框");

        doc = createDocument();
        app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
        var ab = doc.artboards[0].artboardRect;
        ox = ab[0];
        oy = ab[1];

        makeColors();
        loadFonts();

        var bgLayer = doc.layers[0];
        bgLayer.name = "背景 Background";
        drawBackground(bgLayer);

        var imgLayer = doc.layers.add();
        imgLayer.name = "产品图 Image";
        if (imgFile) {
            placeImage(imgLayer, imgFile);
        } else {
            drawPlaceholder(imgLayer);
        }

        var decoLayer = doc.layers.add();
        decoLayer.name = "装饰 Decoration";
        var textLayer = doc.layers.add();
        textLayer.name = "文字 Text";

        drawTitle(decoLayer, textLayer);
        drawItems(textLayer);
        addText(textLayer, "Logo 占位（换成客户 Logo）", CONFIG.logoText, CONFIG.pageWidth - L.left, L.logoBase,
            { size: L.logoSize, color: C.gold, cn: F.cnTitle, en: F.enTitle, tracking: 200, align: Justification.RIGHT });

        report(imgFile);
    }

    // ---------- 文档 ----------

    function createDocument() {
        var preset = new DocumentPreset();
        preset.title = "甜品菜单";
        preset.width = mm(CONFIG.pageWidth);
        preset.height = mm(CONFIG.pageHeight);
        preset.colorMode = DocumentColorSpace.CMYK;
        preset.units = RulerUnits.Millimeters;
        preset.rasterResolution = DocumentRasterResolution.HighResolution;
        preset.numArtboards = 1;
        preset.documentBleedLink = true;
        preset.documentBleedOffset = [mm(CONFIG.bleed), mm(CONFIG.bleed), mm(CONFIG.bleed), mm(CONFIG.bleed)];
        try {
            return app.documents.addDocument(printPresetName(), preset);
        } catch (e) {
            warnings.push("没能自动设置出血，请在 文件 → 文档设置 里把出血设为 " + CONFIG.bleed + " mm。");
            return app.documents.add(DocumentColorSpace.CMYK, mm(CONFIG.pageWidth), mm(CONFIG.pageHeight));
        }
    }

    function printPresetName() {
        var list = app.startupPresetsList;
        for (var i = 0; i < list.length; i++) {
            if (/print|打印|印刷/i.test(list[i])) return list[i];
        }
        return list.length ? list[0] : "Print";
    }

    // ---------- 色板与字体 ----------

    // 用 Spot 对象建色板：PROCESS = 全局印刷色，SPOT = 专色
    function swatch(name, cmyk, isSpot) {
        var color = new CMYKColor();
        color.cyan = cmyk[0];
        color.magenta = cmyk[1];
        color.yellow = cmyk[2];
        color.black = cmyk[3];
        var spot = doc.spots.add();
        spot.name = name;
        spot.color = color;
        spot.colorType = isSpot ? ColorModel.SPOT : ColorModel.PROCESS;
        var sc = new SpotColor();
        sc.spot = spot;
        sc.tint = 100;
        return sc;
    }

    function makeColors() {
        C.dark = swatch("深咖 Dark", CONFIG.colors.dark, false);
        C.glow = swatch("光晕 Glow", CONFIG.colors.glow, false);
        C.gold = swatch(CONFIG.goldAsSpot ? "烫金 Gold Foil" : "香槟金 Gold", CONFIG.colors.gold, CONFIG.goldAsSpot);
        C.cream = swatch("米白 Cream", CONFIG.colors.cream, false);
    }

    function loadFonts() {
        for (var role in FONTS) {
            F[role] = null;
            for (var i = 0; i < FONTS[role].length && !F[role]; i++) {
                try {
                    F[role] = app.textFonts.getByName(FONTS[role][i]);
                } catch (e) {}
            }
            fontReport.push(FONT_LABELS[role] + "：" + (F[role] ? F[role].name : "未找到候选字体，用了默认字体"));
        }
    }

    // ---------- 图形与文字工具 ----------

    function fill(item, color) {
        item.filled = true;
        item.fillColor = color;
        item.stroked = false;
    }

    // box 为 { left, top, right, bottom }，单位 mm
    function rect(container, box) {
        return container.pathItems.rectangle(Y(box.top), X(box.left), mm(box.right - box.left), mm(box.bottom - box.top));
    }

    function circle(container, cx, cy, d) {
        var r = mm(d) / 2;
        return container.pathItems.ellipse(Y(cy) + r, X(cx) - r, 2 * r, 2 * r);
    }

    function bleedBox() {
        var b = CONFIG.bleed;
        return { left: -b, top: -b, right: CONFIG.pageWidth + b, bottom: CONFIG.pageHeight + b };
    }

    function clipTo(group, box) {
        var mask = rect(group, box);
        mask.zOrder(ZOrderMethod.BRINGTOFRONT);
        group.clipped = true;
    }

    // 点文字，(x, base) 为锚点，base 是基线位置；中文字符用 o.cn 字体，其余用 o.en 字体
    function addText(container, name, str, x, base, o) {
        var tf = container.textFrames.pointText([X(x), Y(base)]);
        tf.contents = str;
        tf.name = name;
        var ca = tf.textRange.characterAttributes;
        ca.size = o.size;
        ca.fillColor = o.color;
        ca.tracking = o.tracking || 0;
        if (o.leading) {
            ca.autoLeading = false;
            ca.leading = o.leading;
        }
        tf.textRange.paragraphAttributes.justification = o.align || Justification.LEFT;
        var chars = tf.textRange.characters;
        for (var i = 0; i < chars.length; i++) {
            var font = chars[i].contents.charCodeAt(0) >= 0x2E80 ? o.cn : o.en;
            if (font) chars[i].characterAttributes.textFont = font;
        }
        if (o.opacity) tf.opacity = o.opacity;
        return tf;
    }

    function extend(base, extra) {
        var o = {}, k;
        for (k in base) o[k] = base[k];
        for (k in extra) o[k] = extra[k];
        return o;
    }

    // ---------- 各部分 ----------

    function drawBackground(layer) {
        var base = rect(layer, bleedBox());
        base.name = "底色";
        fill(base, C.dark);

        var grad = doc.gradients.add();
        grad.name = "背景光晕";
        grad.type = GradientType.RADIAL;
        grad.gradientStops[0].rampPoint = 0;
        grad.gradientStops[0].color = C.glow;
        grad.gradientStops[1].rampPoint = 100;
        grad.gradientStops[1].color = C.dark;
        var gc = new GradientColor();
        gc.gradient = grad;

        var group = layer.groupItems.add();
        group.name = "光晕";
        var glow = circle(group, L.glowX, L.glowY, L.glowD);
        glow.stroked = false;
        glow.fillColor = gc;
        clipTo(group, bleedBox());
    }

    function placeImage(layer, file) {
        var box = bleedBox();
        if (CONFIG.imageMode === "bottom") box.top = CONFIG.imageTop;
        var tw = mm(box.right - box.left), th = mm(box.bottom - box.top);

        var group = layer.groupItems.add();
        group.name = "产品图";
        var img = group.placedItems.add();
        img.file = file;

        // 等比铺满（cover），水平居中；full 垂直居中，bottom 贴底
        var s = Math.max(tw / img.width, th / img.height) * 100;
        img.resize(s, s);
        var top = CONFIG.imageMode === "bottom" ? Y(box.bottom) + img.height : Y(box.top) + (img.height - th) / 2;
        img.position = [X(box.left) - (img.width - tw) / 2, top];

        if (CONFIG.embedImage) {
            var oldLevel = app.userInteractionLevel;
            app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
            try {
                img.embed();
            } catch (e) {
                warnings.push("图片没能嵌入，目前是链接状态，图片文件不要移动或删除。");
            } finally {
                app.userInteractionLevel = oldLevel;
            }
        }
        clipTo(group, box);
    }

    function drawPlaceholder(layer) {
        var box = { left: L.left, top: CONFIG.imageTop, right: CONFIG.pageWidth - L.left, bottom: L.placeholderBottom };
        var frame = rect(layer, box);
        frame.name = "产品图占位框（置入图片后删除）";
        frame.filled = false;
        frame.stroked = true;
        frame.strokeColor = C.gold;
        frame.strokeWidth = 0.75;
        frame.strokeDashes = [6, 4];
        addText(layer, "占位说明（置入图片后删除）", "产品图区域\r把 AI 生成的整页图置入「产品图」图层，铺满整页",
            CONFIG.pageWidth / 2, (box.top + box.bottom) / 2,
            { size: 11, leading: 20, color: C.cream, cn: F.cnBody, en: F.enBody, align: Justification.CENTER, opacity: 70 });
    }

    function drawTitle(deco, text) {
        var badge = circle(deco, L.badgeX, L.badgeY, L.badgeD);
        badge.name = "标题圆底";
        fill(badge, C.gold);

        // 中文字面中心约在基线上方 0.38em，据此让字落在圆心
        addText(text, "标题·圆内字", CONFIG.title.badge, L.badgeX, L.badgeY + 0.38 * L.badgeSize / MM,
            { size: L.badgeSize, color: C.dark, cn: F.cnTitle, en: F.enTitle, align: Justification.CENTER });

        var title = addText(text, "标题·中文", CONFIG.title.main, L.mainX, L.mainBase,
            { size: L.mainSize, color: C.cream, cn: F.cnTitle, en: F.enTitle, tracking: 60 });
        var chars = title.textRange.characters;
        if (CONFIG.title.bigIndex >= 0 && CONFIG.title.bigIndex < chars.length) {
            chars[CONFIG.title.bigIndex].characterAttributes.size = L.mainBigSize;
        }

        addText(text, "标题·英文", CONFIG.title.en, L.enX, L.enBase,
            { size: L.enSize, leading: mm(L.enLeading), color: C.gold, cn: F.cnBody, en: F.enTitle, tracking: 80 });
    }

    function drawItems(layer) {
        var body = { color: C.cream, cn: F.cnBody, en: F.enBody };
        var center = extend(body, { align: Justification.CENTER });
        var y = null; // 上一行的基线
        for (var i = 0; i < CONFIG.items.length; i++) {
            var it = CONFIG.items[i], n = i + 1, nameY;
            if (it.unit) {
                var unitY = y === null ? L.listTop : y + L.enToUnit;
                addText(layer, "规格 " + n, it.unit, L.priceX, unitY, extend(center, { size: L.unitSize }));
                nameY = unitY + L.unitToName;
            } else {
                nameY = y === null ? L.listTop + L.unitToName : y + L.itemGap;
            }
            addText(layer, "菜名 " + n, it.cn, L.left, nameY, extend(body, { size: L.nameSize, tracking: 40 }));
            if (it.price) addText(layer, "价格 " + n, it.price, L.priceX, nameY, extend(center, { size: L.priceSize }));
            y = nameY + L.nameToEn;
            if (it.en) addText(layer, "英文名 " + n, it.en, L.left, y, extend(body, { size: L.enNameSize }));
            if (it.descCn) {
                y += L.enToDesc;
                addText(layer, "说明 " + n, it.descCn, L.left, y, extend(body, { size: L.descSize, opacity: 85 }));
            }
            if (it.descEn) {
                y += it.descCn ? L.descLine : L.enToDesc;
                addText(layer, "说明英文 " + n, it.descEn, L.left, y, extend(body, { size: L.descEnSize, opacity: 85 }));
            }
        }
        if (y === null) y = L.listTop;
        if (CONFIG.noteCn) {
            y += L.toNote;
            addText(layer, "备注", CONFIG.noteCn, L.left, y, extend(body, { size: L.noteSize, opacity: 75 }));
        }
        if (CONFIG.noteEn) {
            y += CONFIG.noteCn ? L.noteLine : L.toNote;
            addText(layer, "备注英文", CONFIG.noteEn, L.left, y, extend(body, { size: L.noteEnSize, opacity: 75 }));
        }
    }

    function report(imgFile) {
        var msg = "菜单已生成！\n\n字体：\n" + fontReport.join("\n");
        if (!F.cnBody || !/SourceHan|Noto/.test(F.cnBody.name)) {
            msg += "\n\n建议：在 Creative Cloud → Adobe Fonts 免费激活「思源宋体 Source Han Serif SC」，" +
                "关掉这个文档后重新运行脚本，效果更接近原图。";
        }
        if (!imgFile) msg += "\n\n没有选产品图，已放占位框。之后用 文件 → 置入 把图放进「产品图」图层即可。";
        if (warnings.length) msg += "\n\n注意：\n" + warnings.join("\n");
        msg += "\n\n最后：文件 → 存储为… → Adobe Illustrator (*.AI)";
        alert(msg);
    }

    var oldSystem = app.coordinateSystem;
    try {
        main();
    } catch (e) {
        alert("脚本出错了：\n" + e.message + "\n（第 " + e.line + " 行）\n\n把这个弹窗截图发给 Claude 就能修。");
    } finally {
        app.coordinateSystem = oldSystem;
    }
})();
