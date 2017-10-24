/*

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
            var ucfirst = function(c) {
                return c.replace('-', ' ').toUpperCase();
            };
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
            el.style.fontFeatureSettings = '';

            // Reset element's content to simply a string.
            if (el.querySelectorAll('.layer').length > 0) {
                var originalText = el.querySelector('span').textContent.trim();
                el.textContent = originalText;
            }
            return el;
        },

        init: function(el) {
            if (typeof el === 'number') {
                //jQuery.each(): index in element list
                el = this;
            } else if (el.jquery) {
                //unwrap jquery
                el = el[0];
            }

            var temp, i;
            var rotatedhack = document.documentElement.classList.contains('no-vertical-text');
            var master = Bungee.reset(el);
            var classes = master.className;
            var orientation = master.classList.contains('vertical') ? 'vertical' : 'horizontal';

            function setLayerColor(layer, classname, cssname) {
                var match = classname.match(/^(\w+)-(\w+)(?:-([\d\.]+))?/);

                if (match) {
                    master.classList.add(match[1]);
                    classes += ' ' + match[1];
                    layer.classList.add(match[1]);
                    layer.style[cssname || 'color'] = (match[2].match(/^([0-9a-f]{3}|[0-9a-f]{6})$/i) ? '#' : '') + match[2];
                    if (match[3]) {
                        layer.style.opacity = (parseFloat(match[3])/100).toString();
                    }
                } else {
                    layer.classList.add(classname);
                }

                return layer;
            }

            //remember the content and then get rid of it
            var text = Bungee.cleanupText(master.textContent);
            master.innerHTML = '<div></div>';
            var wrapper = master.firstElementChild;

            //build up a list of opentype features that will be applied to the text
            var ffs = {};

            //first get default styles
            master.style.fontFeatureSettings.split(/,/).forEach(function(tag) {
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
                layers = ['regular', 'outline', 'inline', 'shade'];
                master.classList.add(layers.join(' '));
                classes += ' ' + layers.join(' ');
            }

            var layer, pieces, textWrapper;
            for (i in layers) {
                master.classList.add(layers[i]);
                pieces = layers[i].split('-');
                // don't add multiple children for duplicate classes like "regular" and "regular-ffffff"
                // see if we've already created a layer for this class
                layer = wrapper.querySelector('.layer.' + pieces[0]);
                if (layer) {
                    //if so, only override it if this one has a specific color defined
                    if (pieces.length > 1) {
                        setLayerColor(layer, layers[i]);
                    }
                } else {
                    //haven't seen this layer before, so create one
                    layer = document.createElement('div');
                    layer.classList.add('layer', 'text', pieces[0]);
                    textWrapper = document.createElement('span');
                    textWrapper.textContent = text;
                    layer.appendChild(textWrapper);
                    wrapper.appendChild(layer);
                    setLayerColor(layer, layers[i]);
                }
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
            if (begin || end || master.classList.contains('banner')) {
                //zero out any conflicting classes
                classes = classes.replace(/\b(banner|begin|end|block)(?:-\S+)?/g, ' ');
                master.className = classes;
                if (!(begin in Bungee.beginChars)) {
                    begin = 'square';
                }
                if (!(end in Bungee.endChars)) {
                    end = 'square';
                }
                master.classList.add('sign', 'banner', 'begin-' + begin, 'end-' + end);
                begin = String.fromCharCode(Bungee.beginChars[begin]);
                end = String.fromCharCode(Bungee.endChars[end]);
                var textLayerEl = wrapper.querySelector('.layer.text');

                var bannerWrapper = document.createElement('div');
                bannerWrapper.classList.add('layer', 'sign', 'banner', 'regular');
                var header = document.createElement('header');
                header.innerHTML = begin;
                var figure = document.createElement('figure');
                figure.innerHTML = square;
                var footer = document.createElement('footer');
                footer.innerHTML = end;
                bannerWrapper.appendChild(header);
                bannerWrapper.appendChild(figure);
                bannerWrapper.appendChild(footer);
                textLayerEl.parentNode.insertBefore(bannerWrapper, textLayerEl);

                (function() {
                    //move text after beginning shape
                    var textsize = parseFloat(getComputedStyle(master).fontSize);
                    var left = master.querySelector('.sign header');
                    var main = master.querySelector('.sign figure');

                    //calculate offset for text, apply to all layers
                    var widthAlign = parseFloat(getComputedStyle(left)[widthProp]) / textsize;
                    var textLayers = master.querySelectorAll('.layer.text');
                    Array.prototype.forEach.call(textLayers, function(el) {
                        el.style[leftProp] = widthAlign + 'em';
                    });

                    //expand blocks to fill width
                    var textwidth = parseFloat(getComputedStyle(master.querySelector('.layer.text'))[widthProp]);
                    var squarewidth = parseFloat(getComputedStyle(main)[widthProp]);
                    var numbersquares = Math.ceil(textwidth / squarewidth);
                    var banner = [];
                    for (i = 0; i < numbersquares; i++) {
                        banner.push(square);
                    }
                    main.textContent = banner.join('');
                    main.style[widthProp] = (textwidth / textsize) + 'em';
                })();
            } else if (block || master.classList.contains('block')) {
                //zero out any conflicting classes
                classes = classes.replace(/\b(banner|begin|end|block)(?:-\S+)?/g, ' ');
                master.className = classes;
                if (!(block in Bungee.blockChars)) {
                    block = 'square';
                }
                master.classList.add('sign', 'block', 'block-' + block);
                block = String.fromCharCode(Bungee.blockChars[block]);
                var str = [];
                var length = text.length;
                for (i = 0; i < length; i++) {
                    str.push(block);
                }
                str = str.join('');
                var layerEl = document.createElement('div');
                layerEl.classList.add('layer', 'sign', 'block', 'regular');
                layerEl.innerHTML = str;
                wrapper.prepend(layerEl);

                //turn on block features
                if (orientation === 'horizontal') {
                    ffs.ss01 = '1';
                } else {
                    ffs.vpal = '0';
                }
            }

            //background color
            temp = classes.match(/background-\S+/);
            if (temp) {
                var bg = document.createElement('div');
                bg.classList.add('layer', 'background');
                wrapper.prepend(bg);
                setLayerColor(bg, temp[0], 'backgroundColor');
            }

            //sign color
            var signLayer;
            if (signcolor) {
                signLayer = master.querySelector('.sign');
                if (signLayer) {
                    setLayerColor(signLayer, signcolor);
                }
            }

            // stylistic alternates
            var alts = classes.toLowerCase().match(RegExp("\\balt-(" + Object.keys(Bungee.stylisticAlternates).join('|') + ")\\b", 'g'));
            for (i in alts) {
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
            master.style.fontFeatureSettings = newffs.join(', ');

            //apply accessibility attributes to avoid reading multiple layers to screen readers
            // cf. http://john.foliot.ca/aria-hidden/
            var accLayers = master.querySelectorAll('.layer'), accFirstText = true;
            Array.prototype.forEach.call(accLayers, function(el) {
                // Don't apply ARIA roles to first element in set.
                if (accFirstText && el.classList.contains('text')) {
                    accFirstText = false;
                    return;
                }
                el.setAttribute('aria-hidden', 'true');
                el.setAttribute('role', 'presentation');
            });
        },

        cleanupText: function(text) {
            return text.replace(/\s+/g, ' ').trim();
        }
    };

    //pretty up Bungee elements on document ready
    document.addEventListener('DOMContentLoaded', function() {
        // see if browser support the necessary vertical CSS
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

        if (
            isSafari ||
            isFirefox ||
            !testFeature('font-feature-settings') ||
            !testFeature('writing-mode') ||
            !testFeature('text-orientation')
        ) {
            document.documentElement.classList.add('no-vertical-text');
        }

        var elements = document.querySelectorAll('.bungee');
        Array.prototype.forEach.call(elements, Bungee.init);
    });
})();
