
(function() {
    "use strict";

    $(window).on('load', function() {
        var Bungee = window.Bungee;
        var bungees = $('#typesetter .bungee');
        var allcontrols = $('#controls input');
        var layercontrols = $('#controls input[name=layer]');
        var orientationcontrols = $('#controls input[name=orientation]');
        var sscontrols = $('#controls input[name=ss]');
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
                'font-size': bungees.css('font-size')
            };

            $('.bungee .layer').each(function() {
                styles['.bungee .' + this.className.replace(/ /g, '.').replace('.layer', '')] = {
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
            
            var topclass = bungees.prop('className');
            var allfour = / (regular|inline|outline|shade)/g;
            if (topclass.match(allfour).length === 4) {
                topclass = topclass.replace(allfour, '');
            }
            code += '<div class="' + topclass + '">';
            code += bungees.find('.layer span').first().text().trim();
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
            var url = $('#controls').serialize(); // + '&text=' + encodeURIComponent(bungees.find('span').first().text().trim());
            if (window.history && history.pushState) {
                history.pushState({}, '', '#' + url);
            } else {
                window.location.hash = '#' + url;
            }
        }
        
        function doSVG() {
            var reference = bungees.find('.layer').not('.background');
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
            sscontrols.filter(':checked').each(function() {
                req.ss.push(this.value);
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
    
        function updateLayers(evt) {
            var actor;
            if (evt) {
                //evt will either be a real event, or an element
                actor = evt.target || evt;
            } else {
                actor = textcontrol.get(0);
            }

            var orientation = orientationcontrols.filter(':checked').val();
            var text = false;
            /*
            // SPAN is for live editing
            if (actor.tagName==='SPAN') {
                text = $(evt.target).text();
            } else */ if (actor.tagName === 'LABEL') {
                // this will be called again for the actual input element
                return;
            } else if (textcontrol.is(actor) || actor.tagName !== 'INPUT') {
                text = Bungee.cleanupText(textcontrol.val());
            }
            
            if (text !== false) {
                //text has been edited
                if (!textcontrol.is(actor)) {
                    textcontrol.val(text);
                }
                bungees.find('div > span').each(function() {
                    if (this !== actor) { //changing active element unfocuses element
                        $(this).text(text);
                    }
                });
            }
            
            if (!evt || layercontrols.is(actor)) {
                layercontrols.each(function() {
                    bungees[this.checked ? 'addClass' : 'removeClass'](this.value);
                });
            }
            
            if (!evt || orientationcontrols.is(actor)) {
                bungees.add('.preview').removeClass('horizontal vertical').addClass(orientationcontrols.filter(':checked').val());
            }
            
            if (!evt || sizecontrol.is(actor)) {
                bungees.css('font-size', sizecontrol.val() + 'px');
            }
    
            var begin = backgroundcontrols.filter('[name=begin]:checked').val(),
                end = backgroundcontrols.filter('[name=end]:checked').val(),
                block = backgroundcontrols.filter('[name=block]:checked').val(),
                square = "█",
                bannerstring, beginwidth, squarewidth, textwidth, 
                leftProp = orientation === 'vertical' ? 'top' : 'left',
                widthProp = orientation === 'vertical' ? 'height' : 'width';

            if (backgroundcontrols.is(actor)) {
                if (actor.name === 'block' || actor.value === "") {
                    $('#begin-').prop('checked', true);
                    $('#end-').prop('checked', true);
                    begin = end = "";
                } else {
                    $('#block-').prop('checked', true);
                    block = "";
                }
            }
            
            if (!evt || backgroundcontrols.is(actor) || textcontrol.is(actor) || orientationcontrols.is(actor) || sizecontrol.is(actor)) {
                bungees.removeClass('background block').find('.background.layer').remove();
                bungees.find('.layer').css({'left':'', 'top':''});

                var str;
                if (block) {
                    block = String.fromCharCode(Bungee.blockChars[block]);
                    str = [];
                    for (var i=0, l=Bungee.cleanupText(textcontrol.val()).length; i<l; i++) {
                        str.push(block);
                    }
                    str = str.join('');
                    bungees.addClass('background block');
                    bungees.children().prepend('<div class="background layer regular">' + str + '</div>');
                    bungees.children().prepend('<div class="background layer outline">' + str + '</div>');
                } else if (begin || end) {
                    if (!begin) {
                        begin = end;
                        $('#begin-' + end).prop('checked', true);
                    }
                    if (!end) {
                        end = begin;
                        $('#end-' + begin).prop('checked', true);
                    }

                    begin = String.fromCharCode(Bungee.beginChars[begin]);
                    end = String.fromCharCode(Bungee.endChars[end]);
                    bannerstring = "";
                    if (begin) {
                        bannerstring += begin;
                    }
                    bannerstring += square;
                    if (end) {
                        bannerstring += end;
                    }
                    bungees.addClass('background banner');
                    bungees.children().prepend('<div class="background layer regular"><header>' + begin + '</header><figure>' + square + '</figure><footer>' + end + '</footer></div>');
                    bungees.children().prepend('<div class="background layer outline"><header>' + begin + '</header><figure>' + square + '</figure><footer>' + end + '</footer></div>');
                    setTimeout(function() {
                        //move text after left shape
                        var left = bungees.find('.background.layer').first().find('header');
                        var main = bungees.find('.background.layer').first().find('figure');
                        bungees.find('.layer:not(.background)').css(leftProp, left[widthProp]() + 'px');

                        //expand blocks to fill width
                        var textwidth = bungees.find('.layer:not(.background)').first()[widthProp]();
                        var squarewidth = main[widthProp]();
                        var numbersquares = Math.ceil(textwidth/squarewidth);
                        var remainder = textwidth - (numbersquares-1)*squarewidth;
                        var banner = [];
                        for (var i=0; i<numbersquares; i++) {
                            banner.push(square);
                        }
                        bungees.find('.background.layer figure').text(banner.join(''))[widthProp](textwidth);
                    });
                }
            }

            var ffs = {};

            sscontrols.filter(':checked').each(function() {
                ffs[this.value] = '1';
            });

            if (block) {
                ffs['ss01'] = '1';
                ffs['liga'] = '0';
                ffs['kern'] = '0';
            }
    
            var newffs = [];
            for (var tag in ffs) {
                newffs.push('"' + tag + '" ' + ffs[tag]);
            }
            bungees.css('font-feature-settings', newffs.join(', '));

            if (evt) {
                setURL();
                setTimeout(doCode);
                if (evt.type !== 'input') {
                    // don't update SVG while slider is moving
                    setTimeout(doSVG);
                }
            }
        }
    
        layercontrols.on('change', updateLayers);
        orientationcontrols.on('change', updateLayers);
        sscontrols.on('change', updateLayers);
        sizecontrol.on('input change', updateLayers);
        backgroundcontrols.on('click', updateLayers);
        textcontrol.on('keyup', updateLayers);

        // not doing live editing for now
        //bungees.on('keyup', updateLayers);

        updateLayers();
        doCode();
        doSVG();
    }); //window.onload
})();
