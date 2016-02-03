
(function() {
    "use strict";

    $(window).on('load', function() {
        var Bungee = window.Bungee;
        var preview = $('#typesetter .bungee');
        var allcontrols = $('#controls input');
        var layercontrols = $('#controls input[name=layer]');
        var orientationcontrols = $('#controls input[name=orientation]');
        var rotatedcontrol = $('#controls input[name=rotated]');
        var altcontrols = $('#controls input[name=alt]');
        var sizecontrol = $('#controls input[name=size]');
        var textcontrol = $('#controls input[name=text]');
        var backgroundcontrols = $('#background-controls input');
        var temp;
    
        //process initial url
        if (window.location.hash.length > 1) {
            $('input[type=checkbox], input[type=radio]').prop('checked', false);
            $.each(window.location.hash.substr(1).split('&'), function(i,clause) {
                var eq = clause.split('=', 2);
                switch (eq[0]) {
                    case 'text':
                        textcontrol.val(Bungee.cleanupText(decodeURIComponent(eq[1].replace(/\+/g, '%20'))));
                        break;
                    case 'size':
                        sizecontrol.val(eq[1]);
                        break;
                    default:
                        allcontrols.filter('[name=' + eq[0] + '][value="' + eq[1] + '"]').prop('checked', true);
                        break;
                }
            });
        }

        function doCode() {
            var tab = "  ";
            var code = "";
            
            var styles = {};
            
            styles['.bungee'] = {
                'font-size': preview.css('font-size')
            };

            preview.find('.layer').each(function() {
                styles['.bungee .' + this.className.replace(/\s+/g, '.').replace('.layer', '')] = {
                    'color': $(this).css('color')
                }
            });
            
            code += '<!-- put this stuff inside <head> -->\n';
            code += tab + '<!-- copy these files from resources/web folder -->\n';
            code += tab + '<link rel="stylesheet" href="bungee.css">\n';
            code += tab + '<script src="bungee.js"></script>\n';
            code += tab + '<style>';
            for (var cls in styles) {
                code += '\n';
                code += tab + tab + cls + ' {\n';
                for (var rule in styles[cls]) {
                    code += tab + tab + tab + rule + ': ' + styles[cls][rule] + ';\n';
                }
                code += tab + tab + '}\n';
            }
            code += tab + '</style>\n';
            code += '<!-- end of </head> content -->\n\n';
            
            var topclass = preview.prop('className');
            var allfour = /\b(regular|inline|outline|shade)\b(?!-)/g;
            if (topclass.match(allfour).length === 4) {
                topclass = topclass.replace(allfour, ' ');
            }
            topclass = topclass.replace(/(^|\s)(horizontal|background|block|banner)\b(?!-)/g, ' ');
            topclass = topclass.replace(/\s\s+/g, ' ').trim();
            code += '<div class="' + topclass + '">';
            code += Bungee.cleanupText(textcontrol.val());
            code += '</div>\n';
            
            code = code.replace(/[<>&]/g, function(c) { 
                switch(c) {
                    case '<': return '&lt;';
                    case '>': return '&gt;';
                    case '&': return '&amp;';
                    default: return "&#" + c.charCodeAt(0) + ";";
                }
            });
            
            $('#code').html(code);
        }
    
        function setURL() {
            var url = $('#controls').serialize(); // + '&text=' + encodeURIComponent(preview.find('span').first().text().trim());
            if (window.history && history.pushState) {
                history.pushState({}, '', '#' + url);
            } else {
                window.location.hash = '#' + url;
            }
        }
        
        function doSVG() {
            var reference = preview.find('.layer.text');
            var req = {};
            req.text = Bungee.cleanupText(textcontrol.val()); //reference.find('span').first().text().trim();
            req.size = sizecontrol.val();
            req.orientation = orientationcontrols.filter(':checked').val();
            req.layers = {};
            layercontrols.filter(':checked').each(function() {
                var color = reference.filter('.' + this.value).css('color');
                if (/(\d+),\s*(\d+),\s*(\d+)/.test(color)) {
                    var red = RegExp.$1;
                    var green = RegExp.$2;
                    var blue = RegExp.$3;
                    red = Number(red).toString(16);
                    green = Number(green).toString(16);
                    blue = Number(blue).toString(16);
                    if (red.length===1) { red = '0' + red; }
                    if (green.length===1) { green = '0' + green; }
                    if (blue.length===1) { blue = '0' + blue; }
                    color = red + green + blue;
                }
                req.layers[this.value] = color;
            });
            backgroundcontrols.filter(':checked').each(function() {
                req[this.name] = Bungee[this.name + 'Chars'][this.value];
            })
            req.ss = [];
            altcontrols.filter(':checked').each(function() {
                req.ss.push(Bungee.stylisticAlternates[this.value]);
            });
            req.ss = req.ss.join(',');
            
            $('#svg').html('<img src="/svg.php?' + $.param(req) + '" alt="SVG rendition">');

            req.format = 'png';
            var png = $('<img src="/svg.php?' + $.param(req) + '" alt="PNG rendition">');

            png.on('load', function() {
                var img = $(this);
                img.css({
                    'width': (img.width()/2) + 'px',
                    'height': (img.height()/2) + 'px'
                });
            });

            $('#png').html(png);
            
            req.format='pdf';
            $('#pdf').attr('href', '/svg.php?' + $.param(req));
        }
    
        function updatePreview(evt) {
            var actor;
            if (evt) {
                //evt will either be a real event, or an element
                actor = evt.target || evt;
            } else {
                actor = textcontrol.get(0);
            }

            if (actor.tagName === 'LABEL') {
                // this will be called again for the actual input element
                return;
            }
                        
            var classes = [];
            $.each(preview.prop('className').split(/\s+/), function(i, cls) {
                if (!/^(block|banner|background|begin-.+|end-.+|block-.+|alt-.+|horizontal|vertical|regular|inline|outline|shade)$/.test(cls)) {
                    classes.push(cls);
                }
            });

            var text = Bungee.cleanupText(textcontrol.val());
            
            var layers = layercontrols.filter(':checked');
            if (layers.length < 4) {
                layers.each(function() {
                    classes.push(this.value);
                });
            }

            var orientation = orientationcontrols.filter(':checked').val();
            classes.push(orientation);
            $('.preview').removeClass('horizontal vertical').addClass(orientation);
            
            //rotated mode
            $('html')[rotatedcontrol.prop('checked') ? 'addClass' : 'removeClass']('no-vertical-text');
            
            preview.css('font-size', sizecontrol.val() + 'px');

            //backgrounds
            if (backgroundcontrols.is(actor)) {
                if (actor.name === 'block' || actor.value === "") {
                    $('#begin-').prop('checked', true);
                    $('#end-').prop('checked', true);
                } else {
                    $('#block-').prop('checked', true);
                    if (actor.name === 'begin' && $('#end-').prop('checked')) {
                        $('#end-' + actor.value).prop('checked', true);
                    } else if (actor.name === 'end' && $('#begin-').prop('checked')) {
                        $('#begin-' + actor.value).prop('checked', true);
                    }
                }
            }
            
            var begin=backgroundcontrols.filter('[name=begin]:checked').val(),
                end=backgroundcontrols.filter('[name=end]:checked').val(),
                block=backgroundcontrols.filter('[name=block]:checked').val();
            
            if (begin && end) {
                classes.push('begin-' + begin);
                classes.push('end-' + end);
            } else if (block) {
                classes.push('block-' + block);
            }
            
            //alts
            altcontrols.filter(':checked').each(function() {
                classes.push('alt-' + this.value);
            });
            
            //update the preview!
            preview.prop('className', classes.join(' ')).html(text);
            Bungee.init(preview);

            if (evt) {
                setURL();
                setTimeout(doCode);
                if (evt.type !== 'input') {
                    // don't update SVG while slider is moving
                    setTimeout(doSVG);
                }
            }
        }

        allcontrols.on('change', updatePreview);
        sizecontrol.on('input', updatePreview);
        textcontrol.on('keyup', updatePreview);

        updatePreview();
        doCode();
        doSVG();
    }); //window.onload
})();
