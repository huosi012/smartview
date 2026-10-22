// =====================================================================
//  人员资料导入 / 编辑
//  · 读取 Word(.docx)：每人一段，标题行写“单位-姓名”，下面是简介，照片插在段落里
//  · 读取 Excel(.xlsx)：表头含“姓名 / 单位 / 一句话事迹 / 个人简介 / 照片”
//    照片可以是表格里插入的图片，也可以是一起拖进来的图片文件（按文件名或姓名匹配）
//  · 在表格里核对、修改后，“保存并应用”生成新的大屏文件
//  不依赖任何外部库，离线可用。
// =====================================================================
(function () {
  'use strict';

  var PHOTO_MAX_SIDE = 1600;
  var NS_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  var NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main';
  var NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  var NS_V = 'urn:schemas-microsoft-com:vml';
  var NS_MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006';
  var NS_X = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
  var NS_XDR = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing';
  var NS_REL = 'http://schemas.openxmlformats.org/package/2006/relationships';
  var IMAGE_TYPES = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif', bmp: 'image/bmp', webp: 'image/webp' };

  function each(list, fn) { Array.prototype.forEach.call(list, fn); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function ext(name) { var m = /\.([^.\/]+)$/.exec(name || ''); return m ? m[1].toLowerCase() : ''; }
  function baseName(name) { return String(name || '').replace(/^.*[\\\/]/, '').replace(/\.[^.]+$/, '').trim(); }

  // ---------------------------------------------------------------- ZIP（docx / xlsx 都是 zip 包）

  function readZip(buffer) {
    var dv = new DataView(buffer), u8 = new Uint8Array(buffer), dec = new TextDecoder();
    var eocd = -1;
    for (var i = buffer.byteLength - 22; i >= Math.max(0, buffer.byteLength - 65557); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('文件已损坏，或不是 Office 2007 以后的格式');
    var entries = {}, lower = {};
    var p = dv.getUint32(eocd + 16, true);
    for (var k = dv.getUint16(eocd + 10, true); k > 0 && dv.getUint32(p, true) === 0x02014b50; k--) {
      var nlen = dv.getUint16(p + 28, true);
      var name = dec.decode(u8.subarray(p + 46, p + 46 + nlen));
      entries[name] = { method: dv.getUint16(p + 10, true), size: dv.getUint32(p + 20, true), off: dv.getUint32(p + 42, true) };
      lower[name.toLowerCase()] = name;
      p += 46 + nlen + dv.getUint16(p + 30, true) + dv.getUint16(p + 32, true);
    }
    function find(name) { return entries[name] || entries[lower[String(name).toLowerCase()]]; }
    function bytes(name) {
      var e = find(name);
      if (!e) return Promise.resolve(null);
      var start = e.off + 30 + dv.getUint16(e.off + 26, true) + dv.getUint16(e.off + 28, true);
      var raw = u8.subarray(start, start + e.size);
      if (e.method === 0) return Promise.resolve(raw);
      if (e.method !== 8) return Promise.reject(new Error('不支持的压缩方式'));
      var stream = new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
      return new Response(stream).arrayBuffer().then(function (b) { return new Uint8Array(b); });
    }
    return {
      has: function (name) { return !!find(name); },
      bytes: bytes,
      xml: function (name) {
        return bytes(name).then(function (b) {
          return b ? new DOMParser().parseFromString(dec.decode(b), 'application/xml') : null;
        });
      }
    };
  }

  function resolvePath(dir, target) {
    var out = [];
    (target.charAt(0) === '/' ? target.slice(1) : dir + target).split('/').forEach(function (s) {
      if (s === '..') out.pop(); else if (s && s !== '.') out.push(s);
    });
    return out.join('/');
  }

  // 读取某个部件的关系表：{ rId: 包内路径 }
  function relsOf(zip, part) {
    var cut = part.lastIndexOf('/') + 1;
    var dir = part.slice(0, cut);
    return zip.xml(dir + '_rels/' + part.slice(cut) + '.rels').then(function (doc) {
      var map = {};
      if (doc) each(doc.getElementsByTagNameNS(NS_REL, 'Relationship'), function (r) {
        if (r.getAttribute('TargetMode') !== 'External') map[r.getAttribute('Id')] = resolvePath(dir, r.getAttribute('Target'));
      });
      return map;
    });
  }

  function inFallback(node) {
    for (var n = node.parentNode; n && n.nodeType === 1; n = n.parentNode) {
      if (n.localName === 'Fallback' && n.namespaceURI === NS_MC) return true;
    }
    return false;
  }

  // ---------------------------------------------------------------- 照片：摆正方向、缩小、转 JPEG

  function toPhoto(blob) {
    return createImageBitmap(blob).then(function (bmp) {
      var s = Math.min(1, PHOTO_MAX_SIDE / Math.max(bmp.width, bmp.height));
      var c = document.createElement('canvas');
      c.width = Math.max(1, Math.round(bmp.width * s));
      c.height = Math.max(1, Math.round(bmp.height * s));
      var g = c.getContext('2d');
      g.fillStyle = '#fff';
      g.fillRect(0, 0, c.width, c.height);
      g.drawImage(bmp, 0, 0, c.width, c.height);
      if (bmp.close) bmp.close();
      return c.toDataURL('image/jpeg', 0.88);
    });
  }

  function zipPhoto(zip, path) {
    if (!path || !IMAGE_TYPES[ext(path)]) return Promise.resolve('');
    return zip.bytes(path).then(function (b) {
      return b ? toPhoto(new Blob([b], { type: IMAGE_TYPES[ext(path)] })) : '';
    }).catch(function () { return ''; });
  }

  // ---------------------------------------------------------------- Word

  // 标题行：“单位-姓名”，如“中电华元-李哲”“山东核电 运行一处-代子星”
  var HEADING = /^(.{1,40}?)\s*[-－—–]+\s*([一-龥·•]{2,6})$/;

  function parseDocx(zip) {
    return Promise.all([zip.xml('word/document.xml'), relsOf(zip, 'word/document.xml')]).then(function (r) {
      var doc = r[0], rels = r[1];
      if (!doc) throw new Error('没有找到 Word 正文');

      // 按顺序取出每个段落的文字和图片（跳过兼容性备份内容，避免重复）
      var paras = [];
      each(doc.getElementsByTagNameNS(NS_W, 'p'), function (p) {
        if (inFallback(p)) return;
        var para = { text: '', images: [] };
        (function walk(node) {
          each(node.childNodes, function (n) {
            if (n.nodeType !== 1) return;
            if (n.localName === 'p' && n.namespaceURI === NS_W) return;          // 嵌套段落单独处理
            if (n.localName === 'Fallback' && n.namespaceURI === NS_MC) return;
            if (n.namespaceURI === NS_W) {
              if (n.localName === 't') para.text += n.textContent;
              else if (n.localName === 'tab') para.text += ' ';
              else if (n.localName === 'br' || n.localName === 'cr') para.text += '\n';
            }
            if (n.localName === 'blip' && n.namespaceURI === NS_A) para.images.push(rels[n.getAttributeNS(NS_R, 'embed')]);
            if (n.localName === 'imagedata' && n.namespaceURI === NS_V) para.images.push(rels[n.getAttributeNS(NS_R, 'id')]);
            walk(n);
          });
        })(p);
        paras.push(para);
      });

      var people = [], cur = null, before = [];
      paras.forEach(function (pa) {
        pa.text.split('\n').forEach(function (line) {
          var t = line.replace(/\s+/g, ' ').trim();
          var m = t.length <= 46 && !/[。，；！？,.;!?]$/.test(t) && HEADING.exec(t);
          if (m) {
            cur = { name: m[2], unit: m[1].trim(), bio: [], images: [] };
            people.push(cur);
          } else if (cur && t) {
            cur.bio.push(t);
          }
        });
        pa.images.forEach(function (img) { if (img) (cur ? cur.images : before).push(img); });
      });
      if (!people.length) {
        throw new Error('没有识别到“单位-姓名”格式的标题行。请检查 Word 格式，或改用 Excel 表导入');
      }
      // 照片放在标题前面的写法（最后一人后面没有照片）：整体后移一位
      if (before.length && !people[people.length - 1].images.length) {
        for (var i = people.length - 1; i > 0; i--) people[i].images = people[i - 1].images;
        people[0].images = before;
      } else if (before.length && !people[0].images.length) {
        people[0].images = before;
      }
      return Promise.all(people.map(function (p) {
        return zipPhoto(zip, p.images[0]).then(function (photo) {
          return { name: p.name, unit: p.unit, highlight: '', bio: p.bio.join('\n'), photo: photo };
        });
      }));
    });
  }

  // ---------------------------------------------------------------- Excel

  var COLUMNS = [   // 顺序有讲究：“一句话事迹”要先于“简介/事迹”判断
    ['name', /姓名|名字/],
    ['unit', /单位|部门|处室|公司/],
    ['highlight', /一句话|事迹标题|代言语|亮点|标语/],
    ['photo', /照片|图片|相片/],
    ['bio', /简介|简历|事迹|介绍|内容/]
  ];

  function colIndex(ref) {
    var m = /^([A-Z]+)/.exec(ref || ''), n = 0;
    if (!m) return -1;
    for (var i = 0; i < m[1].length; i++) n = n * 26 + m[1].charCodeAt(i) - 64;
    return n - 1;
  }

  function texts(node) {
    var s = '';
    each(node.getElementsByTagNameNS(NS_X, 't'), function (t) {
      if (t.parentNode.localName !== 'rPh') s += t.textContent;   // 跳过拼音注释
    });
    return s;
  }

  function parseXlsx(zip) {
    var shared = [], sheetPath, rowImages = {}, cellImages = {};
    return Promise.all([zip.xml('xl/workbook.xml'), relsOf(zip, 'xl/workbook.xml'), zip.xml('xl/sharedStrings.xml')]).then(function (r) {
      if (!r[0]) throw new Error('没有找到 Excel 工作表');
      var sheet = r[0].getElementsByTagNameNS(NS_X, 'sheet')[0];
      sheetPath = r[1][sheet && sheet.getAttributeNS(NS_R, 'id')] || 'xl/worksheets/sheet1.xml';
      if (r[2]) each(r[2].getElementsByTagNameNS(NS_X, 'si'), function (si) { shared.push(texts(si)); });
      return Promise.all([zip.xml(sheetPath), relsOf(zip, sheetPath), loadCellImages(zip)]);
    }).then(function (r) {
      var sheetDoc = r[0], sheetRels = r[1];
      cellImages = r[2];
      // 浮动图片：按左上角所在行归到那一行的人
      var drawings = [];
      each(sheetDoc.getElementsByTagNameNS(NS_X, 'drawing'), function (d) {
        var path = sheetRels[d.getAttributeNS(NS_R, 'id')];
        if (path) drawings.push(Promise.all([zip.xml(path), relsOf(zip, path)]));
      });
      return Promise.all(drawings).then(function (list) {
        list.forEach(function (pair) {
          if (!pair[0]) return;
          ['twoCellAnchor', 'oneCellAnchor'].forEach(function (tag) {
            each(pair[0].getElementsByTagNameNS(NS_XDR, tag), function (anchor) {
              var from = anchor.getElementsByTagNameNS(NS_XDR, 'from')[0];
              var blip = anchor.getElementsByTagNameNS(NS_A, 'blip')[0];
              if (!from || !blip) return;
              var row = parseInt(from.getElementsByTagNameNS(NS_XDR, 'row')[0].textContent, 10) + 1;
              if (!rowImages[row]) rowImages[row] = pair[1][blip.getAttributeNS(NS_R, 'embed')];
            });
          });
        });
        return sheetDoc;
      });
    }).then(function (sheetDoc) {
      var rows = [];
      each(sheetDoc.getElementsByTagNameNS(NS_X, 'row'), function (row) {
        var cells = [], images = [];
        each(row.getElementsByTagNameNS(NS_X, 'c'), function (c) {
          var col = colIndex(c.getAttribute('r'));
          if (col < 0) col = cells.length;
          var type = c.getAttribute('t'), v = c.getElementsByTagNameNS(NS_X, 'v')[0], value = '';
          if (type === 's') value = shared[parseInt(v && v.textContent, 10)] || '';
          else if (type === 'inlineStr') value = texts(c);
          else if (v) value = v.textContent;
          var f = c.getElementsByTagNameNS(NS_X, 'f')[0];
          var m = f && /DISPIMG\(\s*"([^"]+)"/.exec(f.textContent);   // WPS 嵌入单元格的图片
          if (m) { if (cellImages[m[1]]) images.push(cellImages[m[1]]); value = ''; }
          cells[col] = String(value).replace(/_x000D_/g, '').replace(/\r\n?/g, '\n').trim();
        });
        rows.push({ n: parseInt(row.getAttribute('r'), 10) || rows.length + 1, cells: cells, images: images });
      });

      // 在前 10 行里找表头
      var head = -1, map = {};
      for (var i = 0; i < Math.min(rows.length, 10) && head < 0; i++) {
        rows[i].cells.forEach(function (text, col) {
          if (!text) return;
          for (var k = 0; k < COLUMNS.length; k++) {
            var key = COLUMNS[k][0];
            if (COLUMNS[k][1].test(text) && map[key] === undefined) { map[key] = col; break; }
          }
        });
        if (map.name !== undefined) head = i; else map = {};
      }
      if (head < 0) throw new Error('Excel 第一行要有表头，至少包含“姓名”一列。可以先点“下载 Excel 表”看模板');

      var people = rows.slice(head + 1).map(function (row) {
        var get = function (key) { return map[key] === undefined ? '' : row.cells[map[key]] || ''; };
        return {
          name: get('name').replace(/\s+/g, ''), unit: get('unit'), highlight: get('highlight'), bio: get('bio'),
          photoName: get('photo'), image: row.images[0] || rowImages[row.n]
        };
      }).filter(function (p) { return p.name; });
      if (!people.length) throw new Error('Excel 里没有读到人员（“姓名”一列是空的）');
      return Promise.all(people.map(function (p) {
        return zipPhoto(zip, p.image).then(function (photo) {
          return { name: p.name, unit: p.unit, highlight: p.highlight, bio: p.bio, photo: photo, photoName: p.photoName };
        });
      }));
    });
  }

  // WPS 的“嵌入单元格图片”：{ 图片ID: 包内路径 }
  function loadCellImages(zip) {
    if (!zip.has('xl/cellimages.xml')) return Promise.resolve({});
    return Promise.all([zip.xml('xl/cellimages.xml'), relsOf(zip, 'xl/cellimages.xml')]).then(function (r) {
      var map = {};
      each(r[0].getElementsByTagNameNS('*', 'cellImage'), function (ci) {
        var pr = ci.getElementsByTagNameNS('*', 'cNvPr')[0], blip = ci.getElementsByTagNameNS(NS_A, 'blip')[0];
        if (pr && blip) map[pr.getAttribute('name')] = r[1][blip.getAttributeNS(NS_R, 'embed')];
      });
      return map;
    });
  }

  // ---------------------------------------------------------------- 生成 Excel（模板 / 导出当前名单）

  var CRC_TABLE = (function () {
    var t = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(u8) {
    var c = 0xFFFFFFFF;
    for (var i = 0; i < u8.length; i++) c = CRC_TABLE[(c ^ u8[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  // 不压缩的 zip（存储方式），足够生成小的 xlsx
  function writeZip(files) {
    var enc = new TextEncoder(), parts = [], central = [], offset = 0;
    files.forEach(function (f) {
      var name = enc.encode(f.name), data = enc.encode(f.text), crc = crc32(data);
      var loc = new DataView(new ArrayBuffer(30));
      loc.setUint32(0, 0x04034b50, true); loc.setUint16(4, 20, true); loc.setUint16(6, 0x0800, true);
      loc.setUint16(12, 0x21, true); loc.setUint32(14, crc, true);
      loc.setUint32(18, data.length, true); loc.setUint32(22, data.length, true); loc.setUint16(26, name.length, true);
      parts.push(new Uint8Array(loc.buffer), name, data);
      var cen = new DataView(new ArrayBuffer(46));
      cen.setUint32(0, 0x02014b50, true); cen.setUint16(4, 20, true); cen.setUint16(6, 20, true); cen.setUint16(8, 0x0800, true);
      cen.setUint16(14, 0x21, true); cen.setUint32(16, crc, true);
      cen.setUint32(20, data.length, true); cen.setUint32(24, data.length, true); cen.setUint16(28, name.length, true);
      cen.setUint32(42, offset, true);
      central.push(new Uint8Array(cen.buffer), name);
      offset += 30 + name.length + data.length;
    });
    var size = central.reduce(function (s, c) { return s + c.length; }, 0);
    var end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
    end.setUint32(12, size, true); end.setUint32(16, offset, true);
    return new Blob(parts.concat(central, [new Uint8Array(end.buffer)]),
      { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  }

  function xmlText(s) {
    return esc(String(s == null ? '' : s).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, ''));
  }

  function buildXlsx(people) {
    var head = ['序号', '姓名', '单位', '一句话事迹（可空）', '个人简介', '照片文件名（可空）'];
    var widths = [6, 10, 18, 30, 70, 18];
    var lines = [head].concat(people.map(function (p, i) {
      return [i + 1, p.name, p.unit, p.highlight, p.bio, ''];
    }));
    var rows = lines.map(function (cells, r) {
      return '<row r="' + (r + 1) + '">' + cells.map(function (v, c) {
        var ref = String.fromCharCode(65 + c) + (r + 1);
        if (typeof v === 'number') return '<c r="' + ref + '" s="2"><v>' + v + '</v></c>';
        return '<c r="' + ref + '" t="inlineStr" s="' + (r ? 2 : 1) + '"><is><t xml:space="preserve">' + xmlText(v) + '</t></is></c>';
      }).join('') + '</row>';
    }).join('');
    var X = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    var R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
    var CT = 'application/vnd.openxmlformats-officedocument.spreadsheetml';
    return writeZip([
      { name: '[Content_Types].xml', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
        '<Default Extension="xml" ContentType="application/xml"/>' +
        '<Override PartName="/xl/workbook.xml" ContentType="' + CT + '.sheet.main+xml"/>' +
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="' + CT + '.worksheet+xml"/>' +
        '<Override PartName="/xl/styles.xml" ContentType="' + CT + '.styles+xml"/></Types>' },
      { name: '_rels/.rels', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Relationships xmlns="' + NS_REL + '"><Relationship Id="rId1" Type="' + R + '/officeDocument" Target="xl/workbook.xml"/></Relationships>' },
      { name: 'xl/workbook.xml', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<workbook xmlns="' + X + '" xmlns:r="' + R + '"><sheets><sheet name="人员资料" sheetId="1" r:id="rId1"/></sheets></workbook>' },
      { name: 'xl/_rels/workbook.xml.rels', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Relationships xmlns="' + NS_REL + '"><Relationship Id="rId1" Type="' + R + '/worksheet" Target="worksheets/sheet1.xml"/>' +
        '<Relationship Id="rId2" Type="' + R + '/styles" Target="styles.xml"/></Relationships>' },
      { name: 'xl/styles.xml', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<styleSheet xmlns="' + X + '"><fonts count="2"><font><sz val="11"/><name val="宋体"/></font><font><b/><sz val="11"/><name val="宋体"/></font></fonts>' +
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>' +
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>' +
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>' +
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs>' +
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>' },
      { name: 'xl/worksheets/sheet1.xml', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<worksheet xmlns="' + X + '"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>' +
        '<cols>' + widths.map(function (w, i) { return '<col min="' + (i + 1) + '" max="' + (i + 1) + '" width="' + w + '" customWidth="1"/>'; }).join('') + '</cols>' +
        '<sheetData>' + rows + '</sheetData></worksheet>' }
    ]);
  }

  function download(doc, blob, name) {
    var a = doc.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    doc.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 60000);
  }

  // ---------------------------------------------------------------- 资料窗口

  var CSS =
    '.svi-backdrop{position:fixed;inset:0;z-index:1000;display:flex;align-items:center;justify-content:center;background:rgba(20,0,2,.72);' +
      'font:14px/1.5 "Microsoft YaHei","微软雅黑","PingFang SC","WenQuanYi Zen Hei",sans-serif;color:#2a1a1a;-webkit-user-select:text;user-select:text}' +
    '.svi-backdrop *{cursor:auto}.svi-backdrop button,.svi-backdrop select,.svi-thumb{cursor:pointer}' +
    '.svi-panel{width:min(1500px,96vw);height:92vh;display:flex;flex-direction:column;background:#fffaf2;border-radius:12px;overflow:hidden;box-shadow:0 20px 80px rgba(0,0,0,.5)}' +
    '.svi-panel.drag{outline:4px dashed #c8161d;outline-offset:-10px}' +
    '.svi-panel header{display:flex;align-items:center;gap:14px;padding:12px 18px;background:#8a0910;color:#fff}' +
    '.svi-panel h2{margin:0;font-size:19px}.svi-count{color:#ffd27a}.svi-panel .svi-x{margin-left:auto;padding:0 6px;background:none;border:0;color:#fff;font-size:30px;line-height:1}' +
    '.svi-bar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:12px 18px;border-bottom:1px solid #ecdcc4}' +
    '.svi-panel button{font:inherit;padding:7px 14px;border-radius:7px;border:1px solid #d9c3a0;background:#fff}' +
    '.svi-panel button.svi-primary{background:#c8161d;border-color:#c8161d;color:#fff;font-weight:bold}' +
    '.svi-panel select{font:inherit;padding:6px 8px;border-radius:7px;border:1px solid #d9c3a0}' +
    '.svi-tip{color:#8a6a4a}' +
    '.svi-msg{padding:10px 18px;background:#fff3dc;border-bottom:1px solid #ecdcc4;white-space:pre-line}.svi-msg:empty{display:none}' +
    '.svi-msg .err{color:#c8161d;font-weight:bold}.svi-msg .ok{color:#1d7a35;font-weight:bold}' +
    '.svi-wrap{flex:1;overflow:auto;padding:0 18px}' +
    '.svi-panel table{width:100%;border-collapse:collapse}' +
    '.svi-panel th{position:sticky;top:0;z-index:1;background:#fffaf2;text-align:left;padding:10px 6px;border-bottom:2px solid #e4cfa8;white-space:nowrap}' +
    '.svi-panel td{padding:8px 6px;border-bottom:1px solid #eee2cf;vertical-align:top}' +
    '.svi-panel td.no{color:#8a6a4a;font-weight:bold;padding-top:14px}' +
    '.svi-panel input,.svi-panel textarea{width:100%;box-sizing:border-box;font:inherit;padding:6px 8px;border:1px solid #d9c3a0;border-radius:6px;background:#fff;resize:vertical}' +
    '.svi-panel input.bad{border-color:#c8161d;background:#fff0f0}' +
    '.svi-thumb{width:84px;height:112px;border-radius:6px;overflow:hidden;display:flex;align-items:center;justify-content:center;text-align:center;' +
      'background:#f1e2c6;color:#9a6a3a;font-size:12px;border:1px solid #d9c3a0}' +
    '.svi-thumb img{width:100%;height:100%;object-fit:cover}.svi-thumb.drag{outline:3px solid #c8161d}' +
    '.svi-ops{white-space:nowrap}.svi-ops button{padding:4px 9px;margin:0 2px}' +
    '.svi-panel footer{display:flex;align-items:center;gap:12px;padding:12px 18px;border-top:1px solid #ecdcc4;background:#fff}' +
    '.svi-note{margin-left:auto;color:#8a6a4a}';

  var GUIDE =
    '支持三种资料，可以一起拖进来：\n' +
    '① Word（.docx）：每人一段，第一行写“单位-姓名”（如“中电华元-李哲”），下面是个人简介，照片插在简介后面。\n' +
    '② Excel（.xlsx）：表头写“姓名、单位、一句话事迹、个人简介、照片文件名”，照片可以直接插在对应行里。点“下载 Excel 表”可得到模板。\n' +
    '③ 照片文件：文件名写成姓名（如“李哲.jpg”），或与 Excel“照片文件名”一列一致，会自动配给对应的人。';

  function open(doc, api) {
    if (doc.querySelector('.svi-backdrop')) return;
    if (!doc.getElementById('svi-style')) {
      var st = doc.createElement('style');
      st.id = 'svi-style';
      st.textContent = CSS;
      doc.head.appendChild(st);
    }
    var cfg = api.config();
    var rows = (cfg.people || []).map(function (p) {
      return { name: p.name || '', unit: p.unit || '', highlight: p.highlight || '', bio: p.bio || '', photo: p.photo || '', focus: p.focus };
    });
    var dirty = false, photoTarget = -1;

    var root = doc.createElement('div');
    root.className = 'svi-backdrop';
    root.innerHTML =
      '<div class="svi-panel">' +
        '<header><h2>人员资料</h2><span class="svi-count"></span><button class="svi-x" data-act="close" title="关闭">×</button></header>' +
        '<div class="svi-bar">' +
          '<button class="svi-primary" data-act="pick">导入 Word / Excel / 照片</button>' +
          '<select data-role="mode"><option value="replace">导入时替换整个名单</option><option value="append">导入时追加到名单后面</option></select>' +
          '<button data-act="template">下载 Excel 表（含当前名单，可作模板）</button>' +
          '<span class="svi-tip">也可以直接把文件拖进这个窗口</span>' +
          '<input type="file" multiple hidden accept=".docx,.xlsx,image/*" data-role="files">' +
          '<input type="file" hidden accept="image/*" data-role="photo">' +
        '</div>' +
        '<div class="svi-msg"></div>' +
        '<div class="svi-wrap"><table><thead><tr><th>#</th><th>照片</th><th style="width:9%">姓名</th><th style="width:13%">单位</th>' +
          '<th style="width:20%">一句话事迹（可空）</th><th>个人简介</th><th></th></tr></thead><tbody></tbody></table></div>' +
        '<footer><button data-act="add">+ 添加一人</button>' +
          '<span class="svi-note">保存时选一个位置，存成新的大屏文件（含全部照片），以后打开新文件使用。</span>' +
          '<button data-act="close">取消</button><button class="svi-primary" data-act="save">保存并应用到大屏</button></footer>' +
      '</div>';
    doc.body.appendChild(root);
    doc.body.classList.add('importing');

    var panel = root.querySelector('.svi-panel');
    var tbody = root.querySelector('tbody');
    var msg = root.querySelector('.svi-msg');
    var filesInput = root.querySelector('[data-role=files]');
    var photoInput = root.querySelector('[data-role=photo]');
    var modeSelect = root.querySelector('[data-role=mode]');

    function say(html) { msg.innerHTML = html; }
    function guide() { say(esc(GUIDE)); }
    function src(photo) {
      if (!photo || /^data:/.test(photo)) return photo;
      try { return new URL(photo, location.href).href; } catch (e) { return photo; }
    }

    function render() {
      tbody.innerHTML = rows.map(function (r, i) {
        return '<tr data-i="' + i + '">' +
          '<td class="no">' + (i + 1) + '</td>' +
          '<td><div class="svi-thumb" data-act="photo" title="点击更换照片，也可以把照片拖到这里">' +
            (r.photo ? '<img src="' + esc(src(r.photo)) + '" alt="">' : '无照片<br>点击添加') + '</div></td>' +
          '<td><input data-f="name" value="' + esc(r.name) + '"' + (r.name ? '' : ' class="bad"') + ' placeholder="必填"></td>' +
          '<td><input data-f="unit" value="' + esc(r.unit) + '"></td>' +
          '<td><textarea data-f="highlight" rows="3">' + esc(r.highlight) + '</textarea></td>' +
          '<td><textarea data-f="bio" rows="5">' + esc(r.bio) + '</textarea></td>' +
          '<td class="svi-ops"><button data-act="up" title="上移">↑</button><button data-act="down" title="下移">↓</button>' +
            '<button data-act="del">删除</button></td>' +
        '</tr>';
      }).join('');
      root.querySelector('.svi-count').textContent = '共 ' + rows.length + ' 人' +
        (rows.filter(function (r) { return !r.photo; }).length ? '，' + rows.filter(function (r) { return !r.photo; }).length + ' 人无照片' : '');
    }

    function close() {
      if (dirty && !doc.defaultView.confirm('修改还没有保存，确定关闭吗？')) return;
      root.remove();
      doc.body.classList.remove('importing');
    }

    // 按文件名或姓名，把照片文件配给对应的人
    function matchPhoto(file) {
      var full = file.name.toLowerCase(), base = baseName(file.name).toLowerCase(), best = -1;
      rows.forEach(function (r, i) {
        var pn = String(r.photoName || '').toLowerCase();
        if (pn && (pn === full || baseName(pn).toLowerCase() === base)) best = i;
      });
      if (best < 0) rows.forEach(function (r, i) { if (r.name && base === r.name.toLowerCase()) best = i; });
      if (best < 0) {
        var len = 0;
        rows.forEach(function (r, i) {
          if (r.name && base.indexOf(r.name.toLowerCase()) >= 0 && r.name.length > len) { best = i; len = r.name.length; }
        });
      }
      return best;
    }

    function importFiles(list) {
      var files = Array.prototype.slice.call(list || []);
      if (!files.length) return;
      var docs = files.filter(function (f) { return /^(docx|xlsx)$/.test(ext(f.name)); });
      var images = files.filter(function (f) { return /^image\//.test(f.type) || IMAGE_TYPES[ext(f.name)]; });
      var skipped = files.filter(function (f) { return docs.indexOf(f) < 0 && images.indexOf(f) < 0; });
      say('正在读取…');

      var notes = [];
      var chain = Promise.resolve([]);
      docs.forEach(function (f) {
        chain = chain.then(function (acc) {
          return f.arrayBuffer().then(function (buf) {
            var zip = readZip(buf);
            return ext(f.name) === 'docx' ? parseDocx(zip) : parseXlsx(zip);
          }).then(function (people) {
            notes.push('<span class="ok">✓</span> 从“' + esc(f.name) + '”识别到 ' + people.length + ' 人');
            return acc.concat(people);
          }).catch(function (e) {
            notes.push('<span class="err">✗ “' + esc(f.name) + '”：' + esc(e.message || e) + '</span>');
            return acc;
          });
        });
      });
      chain.then(function (people) {
        if (people.length) {
          rows = modeSelect.value === 'append' ? rows.concat(people) : people;
          dirty = true;
        }
        var unmatched = [];
        return images.reduce(function (p, file) {
          return p.then(function () {
            var i = matchPhoto(file);
            if (i < 0) { unmatched.push(file.name); return; }
            return toPhoto(file).then(function (photo) { rows[i].photo = photo; dirty = true; })
              .catch(function () { unmatched.push(file.name + '（无法读取）'); });
          });
        }, Promise.resolve()).then(function () {
          if (images.length) notes.push('<span class="ok">✓</span> 配上照片 ' + (images.length - unmatched.length) + ' 张');
          if (unmatched.length) notes.push('<span class="err">以下照片没找到对应的人（文件名请写成姓名）：' + esc(unmatched.join('、')) + '</span>');
          skipped.forEach(function (f) {
            var tip = /^(doc|wps)$/.test(ext(f.name)) ? '请用 Word/WPS 另存为 .docx 再导入'
              : /^(xls|et|csv)$/.test(ext(f.name)) ? '请用 Excel/WPS 另存为 .xlsx 再导入' : '不支持这种文件';
            notes.push('<span class="err">✗ “' + esc(f.name) + '”：' + tip + '</span>');
          });
          var noPhoto = rows.filter(function (r) { return !r.photo; }).map(function (r) { return r.name || '（未填姓名）'; });
          if (noPhoto.length) notes.push('缺少照片：' + esc(noPhoto.join('、')) + '（点表格里的照片框可以补上）');
          if (people.length || images.length) notes.push('请核对下面的内容，可以直接修改，然后点“保存并应用到大屏”。');
          say(notes.join('\n'));
          render();
        });
      });
    }

    root.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-act]');
      if (!btn) return;
      var tr = btn.closest('tr'), i = tr ? +tr.getAttribute('data-i') : -1;
      switch (btn.getAttribute('data-act')) {
        case 'close': close(); break;
        case 'pick': filesInput.value = ''; filesInput.click(); break;
        case 'template':
          download(doc, buildXlsx(rows), (cfg.title || '大屏') + '-人员资料.xlsx');
          break;
        case 'photo': photoTarget = i; photoInput.value = ''; photoInput.click(); break;
        case 'add':
          rows.push({ name: '', unit: '', highlight: '', bio: '', photo: '' });
          dirty = true;
          render();
          tbody.lastElementChild.querySelector('input').focus();
          break;
        case 'up': if (i > 0) { rows.splice(i - 1, 0, rows.splice(i, 1)[0]); dirty = true; render(); } break;
        case 'down': if (i < rows.length - 1) { rows.splice(i + 1, 0, rows.splice(i, 1)[0]); dirty = true; render(); } break;
        case 'del':
          if (doc.defaultView.confirm('删除“' + (rows[i].name || '这一行') + '”？')) { rows.splice(i, 1); dirty = true; render(); }
          break;
        case 'save': save(); break;
      }
    });
    root.addEventListener('input', function (e) {
      var f = e.target.getAttribute('data-f');
      if (!f) return;
      rows[+e.target.closest('tr').getAttribute('data-i')][f] = e.target.value;
      if (f === 'name') e.target.classList.toggle('bad', !e.target.value.trim());
      dirty = true;
    });
    root.addEventListener('keydown', function (e) {
      e.stopPropagation();   // 输入时不触发大屏快捷键
      if (e.key === 'Escape') close();
    });
    filesInput.addEventListener('change', function () { importFiles(filesInput.files); });
    photoInput.addEventListener('change', function () {
      var file = photoInput.files[0], i = photoTarget;
      if (!file || i < 0) return;
      toPhoto(file).then(function (photo) { rows[i].photo = photo; dirty = true; render(); })
        .catch(function () { say('<span class="err">这张照片无法读取：' + esc(file.name) + '</span>'); });
    });

    // 拖放：拖到照片框 = 换这个人的照片；拖到其他地方 = 导入
    panel.addEventListener('dragover', function (e) {
      e.preventDefault();
      panel.classList.add('drag');
      each(root.querySelectorAll('.svi-thumb.drag'), function (t) { t.classList.remove('drag'); });
      var thumb = e.target.closest && e.target.closest('.svi-thumb');
      if (thumb) thumb.classList.add('drag');
    });
    panel.addEventListener('dragleave', function (e) {
      if (!panel.contains(e.relatedTarget)) panel.classList.remove('drag');
    });
    panel.addEventListener('drop', function (e) {
      e.preventDefault();
      panel.classList.remove('drag');
      var thumb = e.target.closest && e.target.closest('.svi-thumb');
      var files = e.dataTransfer.files;
      if (thumb && files.length === 1 && /^image\//.test(files[0].type)) {
        var i = +thumb.closest('tr').getAttribute('data-i');
        toPhoto(files[0]).then(function (photo) { rows[i].photo = photo; dirty = true; render(); });
      } else {
        importFiles(files);
      }
    });

    function save() {
      var missing = rows.filter(function (r) { return !r.name.trim(); });
      if (!rows.length) { say('<span class="err">名单是空的。</span>'); return; }
      if (missing.length) { say('<span class="err">有 ' + missing.length + ' 行没填姓名（红框），请补上或删除。</span>'); return; }
      var people = rows.map(function (r) {
        var p = { name: r.name.trim(), unit: r.unit.trim(), highlight: r.highlight.trim(), bio: r.bio.trim(), photo: r.photo || '' };
        if (r.focus) p.focus = r.focus;
        return p;
      });
      dirty = false;
      say('正在保存…');
      api.save(Object.assign({}, cfg, { people: people }), doc.defaultView).then(function (ok) {
        if (ok) return;
        dirty = true;
        say('<span class="err">已取消保存，修改还没有生效。</span>');
      }, function (e) {
        dirty = true;
        say('<span class="err">保存失败：' + esc(e.message || e) + '</span>');
      });
    }

    if (!api.isBundle) {
      say('<span class="err">提示：当前打开的是开发版 index.html，保存的新文件需要与 assets、importer.js 放在同一文件夹。建议改用 output 里的单文件版来导入。</span>\n' + esc(GUIDE));
    } else {
      guide();
    }
    render();
  }

  window.SmartviewImporter = { open: open, parseDocx: parseDocx, parseXlsx: parseXlsx, readZip: readZip, buildXlsx: buildXlsx };
})();
