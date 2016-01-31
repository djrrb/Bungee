
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
            'box-slant-right': 0xE15F,
            'box-slant-left': 0xE160,
            'chevron-left': 0xE184,
            'chevron-right': 0xE181,
            'chevron-up': 0xE182,
            'chevron-down': 0xE183
        },
        
        backgroundInputList: function(type) {
            var name, unicode, c;
            var list = window.Bungee[type + 'Chars'];
            if (!list) {
                return;
            }
            document.write('<ul><li>');
            document.write('<input id="' + type + '-" type="radio" name="' + type + '" value="" checked>');
            document.write('<label for="' + type + '-">&nbsp;&nbsp;</label>');
            document.write('</li>');
            for (name in list) {
                unicode = list[name];
                c = String.fromCharCode(unicode);
                document.write('<li>');
                document.write('<input id="' + type + '-' + name + '" type="radio" name="' + type + '" value="' + name + '">');
                document.write('<label for="' + type + '-' + name + '">' + c + '</label>');
                document.write('</li>');
            }
            document.write('</ul>');
        },
        
        makeLayers: function(el) {
            if (typeof el === 'number') {
                el = this;
            }
            var master = $(el);
            if (master.find('.layer').length > 0) {
                return;
            }
            //remember the content and then get rid of it
            var text = master.html().trim();
            master.html('<div></div>');
            var wrapper = master.children();
            wrapper.append("<div class='layer background outline'></div>");
            wrapper.append("<div class='layer background regular'></div>");
            wrapper.append("<div class='layer shade'><span>" + text + "</span></div>");
            wrapper.append("<div class='layer outline'><span>" + text + "</span></div>");
            wrapper.append("<div class='layer regular'><span>" + text + "</span></div>");
            wrapper.append("<div class='layer inline'><span>" + text + "</span></div>");

            if (!/shade|outline|regular|inline/.test(el.className)) {
                master.addClass('shade outline regular inline');
            }
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
        $('.bungee').each(Bungee.makeLayers);
    });
})();
