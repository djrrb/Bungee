/*
© 2016 Chris Lewis info@chrislewis.codes

BUILDING BUNGEE LAYOUTS ON THE FLY WITH JAVASCRIPT

Use bungee.js to create a completely styled Bungee layout with a single
element. Various classes on the element determine the appearance.

Example:
    <div class="bungee horizontal regular-efbb43 inline-eae2b1 outline-3e0e00 shade-c9060e background-333333 sign-111111 block-square alt-e alt-rounded" style="font-size: 120px">LAUNDROMAT</div>

Required: 
 * "bungee" — this class determines which elements get this magic applied.

Orientation:
 * "horizontal" or "vertical" — default is horizontal

Layers: 
 * "layer[-color[-opacity]]"
 * layer: background, sign, shade, outline, regular, inline (from "bottom" to "top")
 * color: any valid HTML color, minus the pound sign. Examples: F00, FF0000, red
 * opacity: number from 0 to 100, specifying % opacity. Default 100% opaque.

Block shapes:
 * "block-xxx" where xxx is one of the values in [blockChars] below

Banner mode:
 * "begin-xxx" where xxx is one of the values in [beginChars] below
 * "end-xxx" where xxx is one of the values in [endChars] below

Alternate characters:
 * "alt-xxx" where xxx is one of the values in [stylisticAlternates] below

*/

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
                el.text(el.find('span').first().text().trim());
            }
            return el;
        },
        
        init: function(el) {
            if (typeof el === 'number') {
                el = this;
            }

            var temp;
            var rotatedhack = $('html').hasClass('no-vertical-text');
            var master = Bungee.reset(el);
            var classes = master.prop('className');
            var orientation = master.hasClass('vertical') ? 'vertical' : 'horizontal';

            function setLayerColor(layer, classname, cssname) {
                var match = classname.match(/^(\w+)-(\w+)(?:-([\d\.]+))?/);
                
                if (match) {
                    master.addClass(match[1]);
                    classes += ' ' + match[1];
                    layer.addClass(match[1]);
                    layer.css(cssname || 'color', (match[2].match(/^([0-9a-f]{3}|[0-9a-f]{6})$/i) ? '#' : '') + match[2]);
                    if (match[3]) {
                        layer.css('opacity', (parseFloat(match[3])/100).toString());
                    }
                } else {
                    layer.addClass(classname);
                }
                
                return layer;
            }


            //remember the content and then get rid of it
            var text = Bungee.cleanupText(master.text());
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
                layers = ['regular', 'outline', 'inline', 'shade']
                master.addClass(layers.join(' '));
                classes += ' ' + layers.join(' ');
            }

            var layer;
            for (var i in layers) {
                layer = $("<div class='layer text'><span></span></div>");
                layer.children().text(text); //to avoid special HTML chars
                master.addClass(layers[i]);
                setLayerColor(layer, layers[i]);
                wrapper.append(layer);
            }

            //process banner/block classes
            var begin=(classes.match(/begin-(\S+)/) || ['',''])[1], 
                end=(classes.match(/end-(\S+)/) || ['',''])[1],
                block=(classes.match(/block-(\S+)/) || ['',''])[1], 
                signcolor=(classes.match(/sign-\S+/) || [''])[0],
                square = "█",
                leftProp = orientation === 'vertical' && !rotatedhack ? 'top' : 'left',
                widthProp = orientation === 'vertical' && !rotatedhack ? 'height' : 'width';

            //banners!
            if (begin || end || master.hasClass('banner')) {
                //zero out any conflicting classes
                classes = classes.replace(/\b(banner|begin|end|block)(?:-\S+)?/g, ' ');
                master.prop('className', classes);
                if (!(begin in Bungee.beginChars)) { begin = 'square'; }
                if (!(end in Bungee.endChars)) { end = 'square'; }
                master.addClass('sign banner begin-' + begin + ' end-' + end);
                begin = String.fromCharCode(Bungee.beginChars[begin]);
                end = String.fromCharCode(Bungee.endChars[end]);
                wrapper.children('.layer.text').first().before('<div class="layer sign banner regular"><header>' + begin + '</header><figure>' + square + '</figure><footer>' + end + '</footer></div>');
                (function() {
                    //move text after beginning shape
                    var textsize = parseFloat(master.css('font-size'));
                    var left = master.find('.sign header').first();
                    var main = master.find('.sign figure').first();
                    master.find('.layer.text').css(leftProp, (left[widthProp]()/textsize) + 'em');
                    //expand blocks to fill width
                    var textwidth = master.find('.layer.text').first()[widthProp]();// + 0.1*textsize;
                    var squarewidth = main[widthProp]();
                    var numbersquares = Math.ceil(textwidth/squarewidth);
                    var banner = [];
                    for (var i=0; i<numbersquares; i++) {
                        banner.push(square);
                    }
                    main.text(banner.join('')).css(widthProp, (textwidth/textsize) + 'em');
                })();
            } else if (block || master.hasClass('block')) {
                //zero out any conflicting classes
                classes = classes.replace(/\b(banner|begin|end|block)(?:-\S+)?/g, ' ');
                master.prop('className', classes);
                if (!(block in Bungee.blockChars)) { block = 'square'; }
                master.addClass('sign block block-' + block);
                block = String.fromCharCode(Bungee.blockChars[block]);
                var str = [];
                for (var i=0, l=text.length; i<l; i++) {
                    str.push(block);
                }
                str = str.join('');
                wrapper.prepend('<div class="layer sign block regular">' + str + '</div>');

                //turn on block features
                if (orientation === 'horizontal') {
                    ffs.ss01 = '1';
                } else {
                    ffs.vpal = '0';
                }
            }

            //background color
            if (temp = classes.match(/background-\S+/)) {
                var bg = $("<div class='layer background'></div>").prependTo(wrapper);
                setLayerColor(bg, temp[0], 'background-color');
            }

            
            if (signcolor) {
                setLayerColor(master.find('.sign'), signcolor);
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
            
            //apply accessibility attributes to avoid reading multiple layers to screen readers
            // cf. http://john.foliot.ca/aria-hidden/
            master.find('.layer').attr({
                'aria-hidden': 'true',
                'role': 'presentation'
            });
            
            master.find('.layer.text').first().removeAttr('aria-hidden').removeAttr('role');
        },
        
        cleanupText: function(text) {
            return text.replace(/\s+/g, ' ').trim();
        }
    };

    //pretty up Bungee elements on document ready
    $(function() {
        // see if browser support the necessary vertical CSS
        var hack = false;
        
        function testFeature(feature) {
            var test = document.createElement('div');
            var prefixes = ['', '-ms-', '-webkit-', '-moz-'];
            var camelName = '';
            for (var i in prefixes) {
                camelName = prefixes[i] + feature;
                camelName = camelName.replace(/^-/, '');
                camelName = camelName.replace(/-(.)/g, function(h, c) { return c.toUpperCase(); });
                if (test.style[camelName] !== undefined) {
                    return true;
                }
            }
            return false;
        }

        //browser detection === bad, I know, but Safari is buggy even when it supports writing-mode and font-feature-settings (as of 9.1, Feb 2016)
        var isSafari = navigator.vendor && navigator.vendor.indexOf('Apple') === 0;
        var isFirefox = navigator.userAgent.indexOf('Gecko/') >= 0;
        
        if (isSafari || isFirefox
            || !testFeature('font-feature-settings')
            || !testFeature('writing-mode')
            || !testFeature('text-orientation')
        ) {
            $('html').addClass('no-vertical-text');
        }

        $('.bungee').each(Bungee.init);
    });
})();
