import os
import json
# this script spits out a json file which covers the basic GSUB of the rotated fonts

# ideally this should parse the latest and greatest features.
# however for now it's just a manual copy/paste job



salt_A = 'A.salt Agrave.salt Aacute.salt Acircumflex.salt Atilde.salt Adieresis.salt Aring.salt Amacron.salt Abreve.salt Aogonek.salt AE.salt'.split(' ')

salt_A_off = 'A Agrave Aacute Acircumflex Atilde Adieresis Aring Amacron Abreve Aogonek AE'.split(' ')

salt_E = 'E.salt Egrave.salt Eacute.salt Ecircumflex.salt Edieresis.salt Emacron.salt Ebreve.salt Edotaccent.salt Eogonek.salt Ecaron.salt'.split(' ')

salt_E_off = 'E Egrave Eacute Ecircumflex Edieresis Emacron Ebreve Edotaccent Eogonek Ecaron'.split(' ')

salt_IJ = ['IJ.stack']

salt_IJ_off = ['IJ'];

salt_I = 'I.salt Igrave.salt Iacute.salt Icircumflex.salt Idieresis.salt Itilde.salt Imacron.salt Ibreve.salt Iogonek.salt Idotaccent.salt IJ.salt'.split(' ')

salt_I_off = 'I Igrave Iacute Icircumflex Idieresis Itilde Imacron Ibreve Iogonek Idotaccent IJ.stack'.split(' ')

salt_i_off = 'i igrave iacute icircumflex idieresis itilde imacron ibreve iogonek'.split(' ')


salt_L = 'L.salt Lacute.salt Lcommaaccent.salt Lcaron.salt Ldot.salt Lslash.salt'.split(' ')

salt_L_off = 'L Lacute Lcommaaccent Lcaron Ldot Lslash'.split(' ')

salt_M = ['M.salt']

salt_M_off = ['M']


salt_N = 'N.salt Ntilde.salt Nacute.salt Ncommaaccent.salt Ncaron.salt'.split(' ')

salt_N_off = 'N Ntilde Nacute Ncommaaccent Ncaron'.split(' ')


salt_W = 'W.salt Wcircumflex.salt Wgrave.salt Wacute.salt Wdieresis.salt'.split(' ')

salt_W_off = 'W Wcircumflex Wgrave Wacute Wdieresis'.split(' ')


salt_Y = 'Y.salt Yacute.salt Ycircumflex.salt Ydieresis.salt Ygrave.salt'.split(' ')

salt_Y_off = 'Y Yacute Ycircumflex Ydieresis Ygrave'.split(' ')


salt_X = ['X.salt']

salt_X_off = ['X']

salt_quote = ['quoteleft.salt', 'quoteright.salt'];
salt_quote_off = ['quoteleft', 'quoteright'];

salt_ampersand = ['ampersand.salt'];
salt_ampersand_off = ['ampersand'];



vertical = 'A.v Agrave.v Aacute.v Acircumflex.v Atilde.v Adieresis.v Aring.v Amacron.v Abreve.v Aogonek.v B.v C.v Ccedilla.v Cacute.v Ccircumflex.v Cdotaccent.v Ccaron.v D.v Dcaron.v E.v Egrave.v Eacute.v Ecircumflex.v Edieresis.v Emacron.v Ebreve.v Edotaccent.v Eogonek.v Ecaron.v F.v G.v Gcircumflex.v Gbreve.v Gdotaccent.v Gcommaaccent.v H.v Hcircumflex.v I.v Igrave.v Iacute.v Icircumflex.v Idieresis.v Itilde.v Imacron.v Ibreve.v Iogonek.v Idotaccent.v J.v Jcircumflex.v K.v Kcommaaccent.v L.v Lacute.v Lcommaaccent.v Lcaron.v M.v N.v Ntilde.v Nacute.v Ncommaaccent.v Ncaron.v O.v Ograve.v Oacute.v Ocircumflex.v Otilde.v Odieresis.v Omacron.v Obreve.v Ohungarumlaut.v P.v Q.v R.v Racute.v Rcommaaccent.v Rcaron.v S.v Sacute.v Scircumflex.v Scedilla.v Scaron.v Scommaaccent.v T.v Tcommaaccent.v Tcaron.v U.v Ugrave.v Uacute.v Ucircumflex.v Udieresis.v Utilde.v Umacron.v Ubreve.v Uring.v Uhungarumlaut.v Uogonek.v V.v W.v Wcircumflex.v Wgrave.v Wacute.v Wdieresis.v X.v Y.v Yacute.v Ycircumflex.v Ydieresis.v Ygrave.v Z.v Zacute.v Zdotaccent.v Zcaron.v AE.v Eth.v Oslash.v Thorn.v Dcroat.v Hbar.v IJ.v Ldot.v Lslash.v Eng.v OE.v Tbar.v Germandbls.v A.salt_v Agrave.salt_v Aacute.salt_v Acircumflex.salt_v Atilde.salt_v Adieresis.salt_v Aring.salt_v Amacron.salt_v Abreve.salt_v Aogonek.salt_v E.salt_v Egrave.salt_v Eacute.salt_v Ecircumflex.salt_v Edieresis.salt_v Emacron.salt_v Ebreve.salt_v Edotaccent.salt_v Eogonek.salt_v Ecaron.salt_v I.salt_v Igrave.salt_v Iacute.salt_v Icircumflex.salt_v Idieresis.salt_v Itilde.salt_v Imacron.salt_v Ibreve.salt_v Iogonek.salt_v Idotaccent.salt_v M.salt_v N.salt_v Ntilde.salt_v Nacute.salt_v Ncommaaccent.salt_v Ncaron.salt_v W.salt_v Wcircumflex.salt_v Wgrave.salt_v Wacute.salt_v Wdieresis.salt_v X.salt_v Y.salt_v Yacute.salt_v Ycircumflex.salt_v Ydieresis.salt_v Ygrave.salt_v AE.salt_v IJ.salt_v IJ.stack_v L.salt_v Lacute.salt_v Lcommaaccent.salt_v Lcaron.salt_v Ldot.salt_v Lslash.salt_v block.v'.split(' ')

vertical_off = 'A Agrave Aacute Acircumflex Atilde Adieresis Aring Amacron Abreve Aogonek B C Ccedilla Cacute Ccircumflex Cdotaccent Ccaron D Dcaron E Egrave Eacute Ecircumflex Edieresis Emacron Ebreve Edotaccent Eogonek Ecaron F G Gcircumflex Gbreve Gdotaccent Gcommaaccent H Hcircumflex I Igrave Iacute Icircumflex Idieresis Itilde Imacron Ibreve Iogonek Idotaccent J Jcircumflex K Kcommaaccent L Lacute Lcommaaccent Lcaron M N Ntilde Nacute Ncommaaccent Ncaron O Ograve Oacute Ocircumflex Otilde Odieresis Omacron Obreve Ohungarumlaut P Q R Racute Rcommaaccent Rcaron S Sacute Scircumflex Scedilla Scaron Scommaaccent T Tcommaaccent Tcaron U Ugrave Uacute Ucircumflex Udieresis Utilde Umacron Ubreve Uring Uhungarumlaut Uogonek V W Wcircumflex Wgrave Wacute Wdieresis X Y Yacute Ycircumflex Ydieresis Ygrave Z Zacute Zdotaccent Zcaron AE Eth Oslash Thorn Dcroat Hbar IJ Ldot Lslash Eng OE Tbar Germandbls A.salt Agrave.salt Aacute.salt Acircumflex.salt Atilde.salt Adieresis.salt Aring.salt Amacron.salt Abreve.salt Aogonek.salt E.salt Egrave.salt Eacute.salt Ecircumflex.salt Edieresis.salt Emacron.salt Ebreve.salt Edotaccent.salt Eogonek.salt Ecaron.salt I.salt Igrave.salt Iacute.salt Icircumflex.salt Idieresis.salt Itilde.salt Imacron.salt Ibreve.salt Iogonek.salt Idotaccent.salt M.salt N.salt Ntilde.salt Nacute.salt Ncommaaccent.salt Ncaron.salt W.salt Wcircumflex.salt Wgrave.salt Wacute.salt Wdieresis.salt X.salt Y.salt Yacute.salt Ycircumflex.salt Ydieresis.salt Ygrave.salt AE.salt IJ.salt IJ.stack L.salt Lacute.salt Lcommaaccent.salt Lcaron.salt Ldot.salt Lslash.salt block'.split(' ')

vertical_other = 'space.v commaaccent.v zero.v one.v two.v three.v four.v five.v six.v seven.v eight.v nine.v quoteleft.v quoteright.v quotedblleft.v quotedblright.v quotesinglbase.v quotedblbase.v guilsinglleft.v guilsinglright.v guillemotleft.v guillemotright.v period.v comma.v ellipsis.v exclamdown.v questiondown.v dagger.v daggerdbl.v perthousand.v exclam.v quotedbl.v percent.v ampersand.v ampersand.salt_v quotesingle.v asterisk.v colon.v semicolon.v question.v quoteleft.salt_v quoteright.salt_v'.split(' ')

vertical_other_off = 'space commaaccent zero one two three four five six seven eight nine quoteleft quoteright quotedblleft quotedblright quotesinglbase quotedblbase guilsinglleft guilsinglright guillemotleft guillemotright period comma ellipsis exclamdown questiondown dagger daggerdbl perthousand exclam quotedbl percent ampersand ampersand.salt quotesingle asterisk colon semicolon question quoteleft.salt quoteright.salt'.split(' ')

vertical_sorts = 'hyphen.v braceleft.v endash.v parenright.v emdash.v parenleft.v bracketright.v braceright.v bracketleft.v'.split(' ')

vertical_sorts_off = 'hyphen braceleft endash parenright emdash parenleft bracketright braceright bracketleft'.split(' ')


downer_off = 'I Igrave Iacute Icircumflex Idieresis Itilde Imacron Ibreve Iogonek Idotaccent J Jcircumflex L Lacute Lcommaaccent Lcaron M W Wcircumflex Wgrave Wacute Wdieresis I.salt Igrave.salt Iacute.salt Icircumflex.salt Idieresis.salt Itilde.salt Imacron.salt Ibreve.salt Iogonek.salt Idotaccent.salt L.salt Lacute.salt Lcommaaccent.salt Lcaron.salt Ldot.salt Lslash.salt M.salt W.salt Wcircumflex.salt Wgrave.salt Wacute.salt Wdieresis.salt IJ.salt IJ.stack i igrave iacute icircumflex idieresis itilde imacron ibreve iogonek j jcircumflex l lacute lcommaaccent m w wcircumflex wgrave wacute wdieresis dotlessi'.split(' ')


basedir = os.path.split( os.path.split(__file__)[0] )[0]


feaMap = {
    'ss01': (vertical + vertical_other + vertical_sorts, vertical_off + vertical_other_off + vertical_sorts_off),
    'ss02': (salt_A + salt_M + salt_N + salt_W + salt_X + salt_Y, salt_A_off + salt_M_off + salt_N_off + salt_W_off + salt_X_off + salt_Y_off),
    'ss03': (salt_E, salt_E_off),
    'ss04': (salt_I, salt_I_off),
    'ss05': (salt_L, salt_L_off),
    'ss06': (salt_ampersand, salt_ampersand_off),
    'ss07': (salt_quote, salt_quote_off),
    'ss08': (salt_IJ, salt_IJ_off),
    }
    
keys = sorted(feaMap.keys())
sourcePath = os.path.join(basedir, 'sources/1-drawing/Bungee-Regular.ufo')
try:
    f = OpenFont(sourcePath, showUI=False)
except:
    f = OpenFont(sourcePath)
    
results = {}
for key in keys:
    on, off = feaMap[key]
    offCodes = [f[name].unicodes[0] for name in off]
    onCodes = [f[name].unicodes[0] for name in on]
    results[key] = dict(zip(offCodes, onCodes))
print results

downerCodes = [f[name].unicodes[0] for name in downer_off]

webdir = os.path.join(basedir, 'website')
jsonpath = os.path.join(webdir, 'bungee_gsub.json')

myFile = open(jsonpath, 'wb')
myFile.write(json.dumps(results, sort_keys=True))
myFile.close()

jsonpath = os.path.join(webdir, 'bungee_downer.json')

myFile = open(jsonpath, 'wb')
myFile.write(json.dumps(downerCodes))
myFile.close()