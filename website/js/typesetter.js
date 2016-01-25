
(function() {
    "use strict";

    $(window).on('load', function() {
        var Bungee = window.Bungee;
        var bungees = $('.bungee');
        var allcontrols = $('#controls input');
        var layercontrols = $('#controls input[name=layer]');
        var orientationcontrols = $('#controls input[name=orientation]');
        var sscontrols = $('#controls input[name=ss]');
        var sizecontrol = $('#controls input[name=size]');
        var textcontrol = $('#controls input[name=text]');
        var shapecontrols = $('#shape-controls input');
        var globalCSS;

        var defaultStyles = {};

        var temp = $('<div class="bungee"></div>');
        $('body').append(temp);
        $.each(temp.css('font-feature-settings').split(/,/), function(i, tag) {
            var m = /['"]([a-z]{4})["'](\s+(\d+|on|off))?/.exec(tag);
            if (!m) {
                return;
            }
            if (!m[2] || m[3] === 'on') {
                m[3] = '1';
            } else if (m[3] === 'off') {
                m[3] = '0';
            }
            defaultStyles[m[1]] = m[3];
        });
        temp.remove();
        temp = null;
    
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
            if (!globalCSS) {
                var css = [];
                $.each(document.styleSheets, function(i, ss) {
                    $.each(ss.cssRules, function(j, rule) {
                        if (rule.cssText.indexOf('bungee') >= 0) {
                            css.push(rule.cssText);
                        }
                    });
                });
            
                globalCSS = css.join("\n\n")
                    .replace(/\{\s*/g, "{\n" + tab)
                    .replace(/;\s*/g, ";\n" + tab)
                    .replace(RegExp(tab + "\\}", "g"), "}")
                    .replace(/,\s*url/g, ",\n" + tab + "     url")
                    .replace(/url\((['"]?)http:\/\/\S+\//g, "url($1/path/to/fonts/")
                    .replace(/\n.*?opacity.+?\n/g, "\n")
                    .replace(/\n.+?\{\s*\}/g, "\n")
                    .replace(/\n\n+/g, "\n\n")
                    .trim()
                    ;
            }
            
            var code = "<style>\n" + tab + globalCSS.replace(/(\n+)/g, "$1" + tab) + "\n</style>";
            
            code += '\n\n<div class="bungee">\n' + tab + '<div>\n';
            $('.bungee > div > div').each(function() {
                var div = $(this);
                if (div.closest('.bungee.'+this.className).length) {
                    code += tab + tab + '<div class="' + this.className + '">' + Bungee.cleanupText(textcontrol.val()) + "</div>\n";
                }
            });
            code += tab + "</div>\n</div>";
            
            code = code.replace(/[<>&]/g, function(c) { return "&#" + c.charCodeAt(0) + ";"; });
            
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
            shapecontrols.filter(':checked').each(function() {
                req[this.name] = this.value;
            })
            req.ss = [];
            sscontrols.filter(':checked').each(function() {
                req.ss.push(this.value);
            });
            req.ss = req.ss.join(',');
    
            $('#svg').html('<img src="/svg.php?' + $.param(req) + '" alt="SVG rendition">');
        }
    
        function updateLayers(evt) {
            var actor;
            if (evt) {
                //evt will either be a real event, or an element
                actor = evt.target || evt;
            } else {
                actor = textcontrol.get(0);
            }

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
    
            var begin = shapecontrols.filter('[name=begin]:checked').val(),
                end = shapecontrols.filter('[name=end]:checked').val(),
                shape = shapecontrols.filter('[name=shape]:checked').val(),
                block = "█",
                bannerstring, beginwidth, blockwidth, textwidth;

            if (shapecontrols.is(actor)) {
                if (actor.name === 'shape') {
                    shapecontrols.filter('[name=begin][value=""]').prop('checked',true);
                    shapecontrols.filter('[name=end][value=""]').prop('checked',true);
                    begin = end = "";
                } else {
                    shapecontrols.filter('[name=shape][value=""]').prop('checked',true);
                    shape = "";
                }
            }
            
            if (!evt || shapecontrols.is(actor) || textcontrol.is(actor) || orientationcontrols.is(actor) || sizecontrol.is(actor)) {
                bungees.removeClass('background shapes').find('.background.layer').remove();
                bungees.find('.layer').css('left', '');

                var str;
                if (shape) {
                    shape = String.fromCharCode(shape);
                    str = [];
                    for (var i=0, l=Bungee.cleanupText(textcontrol.val()).length; i<l; i++) {
                        str.push(shape);
                    }
                    str = str.join('');
                    bungees.addClass('background shapes');
                    bungees.children().prepend('<div class="background layer regular">' + str + '</div>');
                    bungees.children().prepend('<div class="background layer outline">' + str + '</div>');
                } else if (begin || end) {
                    begin = String.fromCharCode(begin);
                    end = String.fromCharCode(end);
                    bannerstring = "";
                    if (begin) {
                        bannerstring += String.fromCharCode(begin);
                    }
                    bannerstring += block;
                    if (end) {
                        bannerstring += String.fromCharCode(end);
                    }
                    bungees.addClass('background banner');
                    bungees.children().prepend('<div class="background layer regular"><header>' + begin + '</header><figure>' + block + '</figure><footer>' + end + '</footer></div>');
                    bungees.children().prepend('<div class="background layer outline"><header>' + begin + '</header><figure>' + block + '</figure><footer>' + end + '</footer></div>');
                    setTimeout(function() {
                        //move text after left shape
                        var left = bungees.find('.background.layer').first().find('header');
                        var main = bungees.find('.background.layer').first().find('figure');
                        bungees.find('.layer:not(.background)').css('left', left.width() + 'px');
                        //expand blocks to fill width
                        var textwidth = bungees.find('.layer:not(.background)').first().width();
                        var blockwidth = main.width();
                        var numberblocks = Math.ceil(textwidth/blockwidth);
                        var remainder = textwidth - (numberblocks-1)*blockwidth;
                        var banner = [];
                        for (var i=0; i<numberblocks; i++) {
                            banner.push(block);
                        }
                        bungees.find('.background.layer figure').text(banner.join('')).width(textwidth);
                    });
                }
            }

            var ffs = $.extend({}, defaultStyles);

            sscontrols.filter(':checked').each(function() {
                ffs[this.value] = '1';
            });

            if (shape) {
                ffs['ss01'] = '1';
                ffs['liga'] = '0';
                //ffs['kern'] = '0'; //not necessary per DJR
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
        shapecontrols.on('click', updateLayers);
        textcontrol.on('keyup', updateLayers);

        // not doing live editing for now
        //bungees.on('keyup', updateLayers);

        updateLayers();
        doCode();
        doSVG();
    }); //window.onload
})();
