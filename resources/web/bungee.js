
(function() {
    "use strict";

    var Bungee = window.Bungee = {
        beginChars: {
            'circle': 0x25D6,
            'deco-big': 0xE165,
            'deco': 0xE169,
            'crown': 0xE16D,
            'square': 0xE171,
            'rounded': 0xE175,
            'swallowtail': 0xE185,
            'arrow': 0xE15A
        },
        endChars: {
            'circle': 0x25D7,
            'deco-big': 0xE166,
            'deco': 0xE16A,
            'crown': 0xE16E,
            'square': 0xE172,
            'rounded': 0xE176,
            'swallowtail': 0xE186,
            'arrow': 0x27A1
        },
        blockChars: {
            'square': 0x2B1B,
            'circle': 0x2B24,
            'shield': 0xE15D,
            'box-rounded': 0xE15E,
            'slant-left': 0xE160,
            'slant-right': 0xE15F,
            'chevron-left': 0xE184,
            'chevron-right': 0xE181,
            'chevron-up': 0xE182,
            'chevron-down': 0xE183
        },
        stylisticAlternates: {
            'rounded': 'ss02', 'round': 'ss02',
            'e': 'ss03',
            'i': 'ss04',
            'l': 'ss05',
            'amp': 'ss06', 'ampersand': 'ss06',
            'quote': 'ss07', 'apostrophe': 'ss07',
            'ij': 'ss08'
        },
        
        backgroundInputList: function(type) {
            var name, unicode, c;
            var list = window.Bungee[type + 'Chars'];
            var ucfirst = function(c) { return c.replace('-', ' ').toUpperCase(); };
            if (!list) {
                return;
            }
            document.write('<ul><li>');
            document.write('<input id="' + type + '-" type="radio" name="' + type + '" value="" checked>');
            document.write('<label for="' + type + '-" title="None">&nbsp;&nbsp;</label>');
            document.write('</li>');
            for (name in list) {
                unicode = list[name];
                c = String.fromCharCode(unicode);
                document.write('<li>');
                document.write('<input id="' + type + '-' + name + '" type="radio" name="' + type + '" value="' + name + '">');
                document.write('<label for="' + type + '-' + name + '" title="' + name.replace(/(-|^)\w/g, ucfirst) + '">' + c + '</label>');
                document.write('</li>');
            }
            document.write('</ul>');
        },
        
        reset: function(el) {
            el = $(el);
            el.css('font-feature-settings', '');
            if (el.find('.layer').length > 0) {
                el.html(el.find('span').first().html().trim());
            }
            return el;
        },
        
        init: function(el) {
            if (typeof el === 'number') {
                el = this;
            }

            var temp;
            var master = Bungee.reset(el);
            var classes = master.prop('className');
            var orientation = master.hasClass('vertical') ? 'vertical' : 'horizontal';

            //remember the content and then get rid of it
            var text = Bungee.cleanupText(master.html());
            master.html('<div></div>');
            var wrapper = master.children();

            //build up a list of opentype features that will be applied to the text
            var ffs = {};

            //first get default styles
            $.each(master.css('font-feature-settings').split(/,/), function(i, tag) {
                var m = /['"]([a-z]{4})["'](\s+(\d+|on|off))?/.exec(tag);
                if (!m) {
                    return;
                }
                if (!m[2] || m[3] === 'on') {
                    m[3] = '1';
                } else if (m[3] === 'off') {
                    m[3] = '0';
                }
                ffs[m[1]] = m[3];
            });

            //add the text layers
            var layers = classes.match(/\b(regular|inline|outline|shade)(-\S+)?/gi);
            if (!layers) {
                master.addClass('regular inline outline shade');
                classes += ' regular inline outline shade';
            }
            var match, layer;
            for (var i in layers) {
                layer = $("<div class='layer text'><span>" + text + "</span></div>");
                master.addClass(layers[i]);
                if (match = layers[i].match(/^(\w+)-(\S+)/)) {
                    master.addClass(match[1]);
                    layer.addClass(match[1]);
                    layer.css('color', (match[2].match(/^([0-9a-f]{3}|[0-9a-f]{6})$/i) ? '#' : '') + match[2]);
                } else {
                    layer.addClass(layers[i]);
                }
                wrapper.append(layer);
            }

            //process banner/block classes
            var begin=(classes.match(/begin-(\S+)/) || ['',''])[1], 
                end=(classes.match(/end-(\S+)/) || ['',''])[1],
                block=(classes.match(/block-(\S+)/) || ['',''])[1], 
                square = "█",
                leftProp = orientation === 'vertical' ? 'top' : 'left',
                widthProp = orientation === 'vertical' ? 'height' : 'width';

            //banners!
            if (begin || end || master.hasClass('banner')) {
                //zero out any conflicting classes
                classes = classes.replace(/(^|\s)(background|banner|begin-\S+|end-\S+|block|block-\S+)($|\s)/g, ' ');
                master.prop('className', classes);
                if (!(begin in Bungee.beginChars)) { begin = 'square'; }
                if (!(end in Bungee.endChars)) { end = 'square'; }
                master.addClass('background banner begin-' + begin + ' end-' + end);
                begin = String.fromCharCode(Bungee.beginChars[begin]);
                end = String.fromCharCode(Bungee.endChars[end]);
                wrapper.prepend('<div class="background layer regular"><header>' + begin + '</header><figure>' + square + '</figure><footer>' + end + '</footer></div>');
                wrapper.prepend('<div class="background layer outline"><header>' + begin + '</header><figure>' + square + '</figure><footer>' + end + '</footer></div>');
                //give browser a second to lay everything out, then position text
                master.css('visibility', 'hidden'); //hide the dirty work
                setTimeout(function() { master.css('visibility', ''); }, 100);
                setTimeout(function() {
                    //move text after beginning shape
                    var left = master.find('.background header').first();
                    var main = master.find('.background figure').first();
                    master.find('.text').css(leftProp, left[widthProp]() + 'px');
                    //expand blocks to fill width
                    var textsize = parseFloat(master.css('font-size'));
                    var textwidth = master.find('.layer.text').first()[widthProp]();// + 0.1*textsize;
                    var squarewidth = main[widthProp]();
                    var numbersquares = Math.ceil(textwidth/squarewidth);
                    var banner = [];
                    for (var i=0; i<numbersquares; i++) {
                        banner.push(square);
                    }
                    master.find('.background figure').text(banner.join(''))[widthProp](textwidth);
                }, 10);
            } else if (block || master.hasClass('block')) {
                //zero out any conflicting classes
                classes = classes.replace(/(^|\s)(background|banner|begin-\S+|end-\S+|block|block-\S+)($|\s)/g, ' ');
                master.prop('className', classes);
                if (!(block in Bungee.blockChars)) { block = 'square'; }
                master.addClass('background block block-' + block);
                block = String.fromCharCode(Bungee.blockChars[block]);
                var str = [];
                for (var i=0, l=text.length; i<l; i++) {
                    str.push(block);
                }
                str = str.join('');
                wrapper.prepend('<div class="background layer regular">' + str + '</div>');
                wrapper.prepend('<div class="background layer outline">' + str + '</div>');

                //turn on block features
                ffs['ss01'] = '1';
                ffs['liga'] = '0';
                ffs['kern'] = '0';
            }
            
            // stylistic alternates
            var alts = classes.toLowerCase().match(RegExp("\\balt-(" + Object.keys(Bungee.stylisticAlternates).join('|') + ")\\b", 'g'));
            for (var i in alts) {
                temp = alts[i].substr(4);
                if (temp in Bungee.stylisticAlternates) {
                    ffs[Bungee.stylisticAlternates[temp]] = '1';
                }
            }

            //apply the complete font-feature-settings
            var newffs = [];
            for (var tag in ffs) {
                newffs.push('"' + tag + '" ' + ffs[tag]);
            }
            master.css('font-feature-settings', newffs.join(', '));
        },
        
        cleanupText: function(text) {
            return text.replace(/\s+/g, ' ').trim();
        }
    };

    //pretty up Bungee elements on document ready
    $(function() {
        // see if browser support writing-mode
        var test = $('<div class="bungee vertical" style="display:none"></div>');
        $('body').append(test);
        if (!test.css('writing-mode')) {
            $('html').addClass('no-vertical-text');
        }
        test.remove();
        $('.bungee').each(Bungee.init);
    });
})();
