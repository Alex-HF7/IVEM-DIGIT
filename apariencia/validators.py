import math
import re
from io import BytesIO
from xml.etree.ElementTree import TreeBuilder
from PIL import Image, UnidentifiedImageError
from defusedxml import ElementTree
from django.core.exceptions import ValidationError
from .specs import MAX_IMAGE_BYTES, SLOTS

class StaticSVGTreeBuilder(TreeBuilder):
    def __init__(self):
        super().__init__()
        self.count=0
        self.depth=0

    def start(self,tag,attrs):
        self.count+=1
        self.depth+=1
        if self.count>10000 or self.depth>100:
            raise ValidationError('El SVG es demasiado complejo. Exporta una versión simplificada.')
        return super().start(tag,attrs)

    def end(self,tag):
        node=super().end(tag)
        self.depth-=1
        return node

    def pi(self,target,text=None):
        raise ValidationError('No se permiten instrucciones XML ni hojas de estilo externas en SVG.')


SVG_NS = 'http://www.w3.org/2000/svg'
TAGS = {'svg','g','defs','path','rect','circle','ellipse','line','polyline','polygon',
        'clipPath','mask','linearGradient','radialGradient','stop','pattern','symbol','use',
        'title','desc','text','tspan'}
ATTRS = {'id','d','x','y','x1','y1','x2','y2','cx','cy','r','rx','ry','width','height',
         'viewBox','preserveAspectRatio','transform','fill','fill-rule','fill-opacity',
         'stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-miterlimit',
         'stroke-dasharray','stroke-dashoffset','stroke-opacity','opacity','clip-path',
         'clip-rule','mask','gradientUnits','gradientTransform','offset','stop-color',
         'stop-opacity','fx','fy','fr','spreadMethod','patternUnits','patternContentUnits',
         'patternTransform','clipPathUnits','maskUnits','maskContentUnits','points','href','version','font-family','font-size','font-weight',
         'text-anchor','dominant-baseline','dx','dy','letter-spacing','style'}
STYLE_PROPS = {'fill','fill-rule','fill-opacity','stroke','stroke-width','stroke-linecap',
               'stroke-linejoin','stroke-opacity','opacity','stop-color','stop-opacity',
               'font-family','font-size','font-weight','text-anchor'}


def safe_value(value):
    if any(token in value.lower() for token in ['javascript:', 'data:', 'http:', 'https:', '/*', '\\', '@', '<', '>']):
        raise ValidationError('El SVG contiene referencias o estilos no permitidos.')
    if re.search(r'url\s*\(',value,re.I) and not re.fullmatch(r'url\(\s*#[A-Za-z_][\w:.-]*\s*\)',value,re.I):
        raise ValidationError('El SVG solo puede referenciar elementos dentro de la misma imagen.')


def length(value):
    match=re.fullmatch(r'\s*([0-9]+(?:\.[0-9]+)?)(px|pt|mm|cm|in)?\s*',value or '')
    if not match: raise ValidationError('Usa dimensiones SVG en px o un viewBox con las medidas originales.')
    return float(match[1])*{'px':1,None:1,'pt':96/72,'mm':96/25.4,'cm':96/2.54,'in':96}[match[2]]


def validate_image(upload, slot):
    if slot not in SLOTS: raise ValidationError('Tipo de imagen no válido.')
    if upload.size > MAX_IMAGE_BYTES: raise ValidationError('La imagen no puede superar 5 MB.')
    try:
        upload.seek(0)
        raw=upload.read(MAX_IMAGE_BYTES+1)
        if len(raw)>MAX_IMAGE_BYTES: raise ValidationError('La imagen no puede superar 5 MB.')
        suffix=upload.name.rsplit('.',1)[-1].lower()
        if suffix=='svg':
            try:
                parser=ElementTree.DefusedXMLParser(target=StaticSVGTreeBuilder(),forbid_dtd=True,forbid_entities=True,forbid_external=True)
                parser.feed(raw)
                root=parser.close()
            except Exception as error:
                raise ValidationError('SVG no válido. No se permiten entidades XML ni recursos externos.') from error
            nodes=list(root.iter())
            if root.tag != '{'+SVG_NS+'}svg' or len(nodes)>10000:
                raise ValidationError('Usa un SVG simple con espacio de nombres SVG válido.')
            for node in nodes:
                if not node.tag.startswith('{'+SVG_NS+'}') or node.tag.split('}')[-1] not in TAGS:
                    raise ValidationError('El SVG contiene elementos no permitidos. Exporta una versión SVG simple.')
                for key,value in node.attrib.items():
                    if key.startswith('{') and key not in {'{http://www.w3.org/1999/xlink}href','{http://www.w3.org/XML/1998/namespace}space'}:
                        raise ValidationError('El SVG contiene atributos de otro formato.')
                    key=key.split('}')[-1]
                    if key=='space' and value in {'default','preserve'}: continue
                    if key not in ATTRS: raise ValidationError('El SVG contiene atributos no permitidos.')
                    if key=='href' and not re.fullmatch(r'#[A-Za-z_][\w:.-]*',value):
                        raise ValidationError('El SVG no puede enlazar recursos externos.')
                    if key=='style':
                        for declaration in filter(str.strip,value.split(';')):
                            prop,sep,val=declaration.partition(':')
                            if not sep or prop.strip().lower() not in STYLE_PROPS:
                                raise ValidationError('El SVG contiene estilos no permitidos.')
                            safe_value(val)
                    else: safe_value(value)
            box=None
            if 'viewBox' in root.attrib:
                try:
                    box=[float(part) for part in re.split(r'[\s,]+',root.get('viewBox','').strip())]
                    if len(box)!=4 or not all(math.isfinite(part) for part in box) or min(box[2:])<=0:raise ValueError
                except ValueError as error:
                    raise ValidationError('El viewBox del SVG no es válido.') from error
            if 'width' in root.attrib or 'height' in root.attrib:
                width,height=length(root.get('width')),length(root.get('height'))
            else:
                if box is None:raise ValidationError('El SVG necesita width/height o un viewBox válido.')
                width,height=box[2:]
            if not all(math.isfinite(value) and value>0 for value in [width,height]):
                raise ValidationError('Las dimensiones de la imagen no son válidas.')
            mime='image/svg+xml'; extension='svg'; tolerance=.02
        elif suffix in {'png','jpg','jpeg'}:
            try:
                with Image.open(BytesIO(raw)) as image:
                    width,height=image.size
                    expected='PNG' if suffix=='png' else 'JPEG'
                    if image.format!=expected: raise ValueError
                    ew,eh=SLOTS[slot][2:]
                    if abs(width-ew)>.51 or abs(height-eh)>.51:
                        raise ValidationError(f'Medidas incorrectas: usa {ew} × {eh}. Recibido: {width} × {height}.')
                    image.verify()
                with Image.open(BytesIO(raw)) as decoded:
                    if getattr(decoded,'is_animated',False):raise ValidationError('Usa una imagen estática, sin animación.')
                    if decoded.getexif().get(274,1)!=1:raise ValidationError('Exporta la imagen con su orientación aplicada, sin rotación EXIF.')
                    decoded.load()
            except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,SyntaxError) as error:
                raise ValidationError('La imagen PNG/JPEG no es válida.') from error
            mime='image/png' if suffix=='png' else 'image/jpeg'
            extension='png' if suffix=='png' else 'jpg'; tolerance=.51
        else:
            raise ValidationError('Sube una imagen SVG, PNG o JPEG. Se recomienda SVG.')
        expected_width,expected_height=SLOTS[slot][2:]
        if abs(width-expected_width)>tolerance or abs(height-expected_height)>tolerance:
            raise ValidationError(f'Medidas incorrectas: usa {expected_width} × {expected_height}. Recibido: {width:g} × {height:g}.')
        return {'width':width,'height':height,'mime':mime,'extension':extension}
    finally:
        upload.seek(0)


def luminance(color):
    values=[int(color[index:index+2],16)/255 for index in (1,3,5)]
    values=[value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in values]
    return sum(value*weight for value,weight in zip(values,(.2126,.7152,.0722)))


def contrast(first,second):
    a,b=sorted((luminance(first),luminance(second)))
    return (b+.05)/(a+.05)


def on_color(color):
    return '#ffffff' if contrast(color,'#ffffff')>=contrast(color,'#000000') else '#000000'
