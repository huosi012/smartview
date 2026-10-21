/**
 * 在装有 Adobe Illustrator 的电脑上，把 .svg / .pdf / PDF 兼容的 .ai 另存为 Illustrator 原生 .ai。
 *
 * 为什么需要它：aiexport 生成的 .ai 能被 Illustrator 直接打开、全部可编辑，但没有图层、转曲后不能改字。
 * 客户如果要「分图层、能改文字」的原生源文件，就用本脚本处理 SVG 设计稿：
 *   - SVG 的顶层 <g id="背景"> <g id="文字"> … 会变成同名图层
 *   - SVG 的 <text> 保留为可编辑文字（客户电脑上需要有对应字体）
 *
 * 用法一（手动批量）：Illustrator → 文件 → 脚本 → 其他脚本…，选本文件，
 *   依次选择源文件夹和输出文件夹。
 *
 * 用法二（给 Illustrator MCP / 其他脚本调用，不弹对话框）：
 *   var AIEXPORT_NO_UI = true;
 *   $.evalFile("/path/to/save_as_native_ai.jsx");
 *   saveAsNativeAi("/path/card.svg", "/path/card.ai", { cmyk: true, outlineText: false });
 */
#target illustrator

var AIEXPORT_DEFAULTS = {
    cmyk: true,          // 文档颜色模式转为 CMYK（印刷）
    outlineText: false,  // 文字转曲；客户要改字就保持 false
    pdfCompatible: true  // 保存 PDF 兼容内容，便于其他软件预览
};

function saveAsNativeAi(sourcePath, targetPath, settings) {
    var opts = {};
    for (var key in AIEXPORT_DEFAULTS) {
        opts[key] = settings && settings[key] !== undefined ? settings[key] : AIEXPORT_DEFAULTS[key];
    }
    var doc = app.open(new File(sourcePath));
    try {
        if (opts.cmyk && doc.documentColorSpace !== DocumentColorSpace.CMYK) {
            app.executeMenuCommand("doc-color-cmyk");
        }
        for (var i = doc.placedItems.length - 1; i >= 0; i--) {
            doc.placedItems[i].embed();  // 链接图片嵌入文件，避免客户打开时缺图
        }
        if (opts.outlineText) {
            for (var j = doc.textFrames.length - 1; j >= 0; j--) {
                var frame = doc.textFrames[j];
                if (!frame.locked && !frame.hidden && !frame.layer.locked) {
                    frame.createOutline();
                }
            }
        }
        var save = new IllustratorSaveOptions();
        if (typeof Compatibility.ILLUSTRATOR17 !== "undefined") {
            save.compatibility = Compatibility.ILLUSTRATOR17;  // Illustrator CC：新旧版本都能打开
        }
        save.pdfCompatible = opts.pdfCompatible;
        save.embedICCProfile = true;
        save.embedLinkedFiles = true;
        save.compressed = true;
        save.fontSubsetThreshold = 100;
        doc.saveAs(new File(targetPath), save);
    } finally {
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
    return targetPath;
}

function aiexportBatch() {
    var source = Folder.selectDialog("选择设计稿所在文件夹（.svg / .pdf / .ai）");
    if (!source) return;
    var target = Folder.selectDialog("选择原生 .ai 的输出文件夹");
    if (!target) return;
    var files = source.getFiles(function (f) {
        return f instanceof File && /\.(svg|pdf|ai)$/i.test(f.name);
    });
    if (!files.length) {
        alert("文件夹里没有 .svg / .pdf / .ai 文件");
        return;
    }

    var previous = app.userInteractionLevel;
    app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
    var done = [], failed = [];
    try {
        for (var i = 0; i < files.length; i++) {
            var name = files[i].name.replace(/\.[^.]+$/, "") + ".ai";
            try {
                saveAsNativeAi(files[i].fsName, target.fsName + "/" + name);
                done.push(name);
            } catch (e) {
                failed.push(files[i].name + "：" + e.message);
            }
        }
    } finally {
        app.userInteractionLevel = previous;
    }
    alert("完成 " + done.length + " 个" + (failed.length ? "\n失败 " + failed.length + " 个：\n" + failed.join("\n") : ""));
}

if (typeof AIEXPORT_NO_UI === "undefined" || !AIEXPORT_NO_UI) {
    aiexportBatch();
}
