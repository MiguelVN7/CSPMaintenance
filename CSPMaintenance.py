from constraint import Problem
import sys
import os

def extraer_posiciones(linea):
    posiciones = linea.strip().split(':')[1].strip().split()
    posiciones = [tuple(map(int, pos.strip('()').split(','))) for pos in posiciones]
    return posiciones

def leer_archivo_entrada(ruta_archivo):
    with open(ruta_archivo, 'r', encoding='utf-8') as archivo:
        lineas = archivo.readlines()
    print("Contenido del archivo:", lineas)  # Depuración

    # Procesar cada línea para extraer la información
    franjas = int(lineas[0].strip().split(':')[1])
    matriz_tamano = lineas[1].strip()
    filas, columnas = map(int, matriz_tamano.split('x'))
    talleres_std = extraer_posiciones(lineas[2])
    talleres_spc = extraer_posiciones(lineas[3])
    parkings = extraer_posiciones(lineas[4])

    aviones = []
    for linea in lineas[5:]:
        if linea.strip():
            datos_avion = linea.strip().split('-')
            avion = {
                'id': datos_avion[0],
                'tipo': datos_avion[1],
                'restriccion_orden': datos_avion[2] == 'T',
                'tareas_tipo1': int(datos_avion[3]),
                'tareas_tipo2': int(datos_avion[4]),
            }
            aviones.append(avion)

    return franjas, (filas, columnas), talleres_std, talleres_spc, parkings, aviones

def determinar_dominio(avion, f, franjas, talleres_std, talleres_spc, parkings):
    dominio = []
    if avion['restriccion_orden']:
        # Tareas de tipo 2 primero
        if f < avion['tareas_tipo2']:
            # Debe realizar tareas de tipo 2 en talleres SPC
            dominio += [f"SPC{pos}" for pos in talleres_spc]
        elif f < avion['tareas_tipo2'] + avion['tareas_tipo1']:
            # Después, tareas de tipo 1 en talleres STD o SPC
            dominio += [f"STD{pos}" for pos in talleres_std] + [f"SPC{pos}" for pos in talleres_spc]
        else:
            # Sin tareas pendientes, puede ir a parkings
            dominio += [f"PRK{pos}" for pos in parkings]
    else:
        tareas_totales = avion['tareas_tipo1'] + avion['tareas_tipo2']
        if f < tareas_totales:
            # Tiene tareas pendientes
            dominio += [f"STD{pos}" for pos in talleres_std] + [f"SPC{pos}" for pos in talleres_spc]
        else:
            # Sin tareas pendientes, puede ir a parkings
            dominio += [f"PRK{pos}" for pos in parkings]
    return dominio

def restriccion_capacidad_taller(problem, talleres_std, talleres_spc, aviones, franjas):
    for f in range(franjas):
        for taller in talleres_std:
            variables_taller = []
            for avion in aviones:
                nombre_variable = f"X_{avion['id']}_{f}"
                variables_taller.append(nombre_variable)
            def restriccion(*asignaciones):
                conteo_total = 0
                conteo_jumbo = 0
                for asignacion, avion in zip(asignaciones, aviones):
                    if asignacion == f"STD{taller}":
                        conteo_total += 1
                        if avion['tipo'] == 'JMB':
                            conteo_jumbo += 1
                if conteo_total > 2 or conteo_jumbo > 1:
                    return False
                return True
            problem.addConstraint(restriccion, variables_taller)
        for taller in talleres_spc:
            variables_taller = []
            for avion in aviones:
                nombre_variable = f"X_{avion['id']}_{f}"
                variables_taller.append(nombre_variable)
            def restriccion(*asignaciones):
                conteo_total = 0
                conteo_jumbo = 0
                for asignacion, avion in zip(asignaciones, aviones):
                    if asignacion == f"SPC{taller}":
                        conteo_total += 1
                        if avion['tipo'] == 'JMB':
                            conteo_jumbo += 1
                if conteo_total > 2 or conteo_jumbo > 1:
                    return False
                return True
            problem.addConstraint(restriccion, variables_taller)

def restriccion_adyacencia(problem, aviones, franjas, posiciones_dict):
    for f in range(franjas):
        variables_franja = [f"X_{avion['id']}_{f}" for avion in aviones]
        def restriccion(*asignaciones):
            asignaciones_por_pos = {}
            for asignacion in asignaciones:
                if asignacion not in asignaciones_por_pos:
                    asignaciones_por_pos[asignacion] = 0
                asignaciones_por_pos[asignacion] += 1

            for asignacion in asignaciones:
                # Obtener posiciones adyacentes
                adyacentes = posiciones_dict.get(asignacion, [])
                # Verificar que al menos una posición adyacente esté libre
                if not any(pos not in asignaciones_por_pos for pos in adyacentes):
                    return False
            return True
        problem.addConstraint(restriccion, variables_franja)

def restriccion_jumbos_no_adyacentes(problem, aviones_jumbo, franjas, posiciones_dict):
    for f in range(franjas):
        variables_jumbo = [f"X_{avion['id']}_{f}" for avion in aviones_jumbo]
        def restriccion(*asignaciones):
            for i, asignacion1 in enumerate(asignaciones):
                for j, asignacion2 in enumerate(asignaciones):
                    if i != j:
                        # Verificar si están en la misma posición o posiciones adyacentes
                        if asignacion1 == asignacion2 or asignacion1 in posiciones_dict.get(asignacion2, []):
                            return False
            return True
        problem.addConstraint(restriccion, variables_jumbo)

def restriccion_tareas_y_orden(problem, avion, franjas):
    variables_avion = [f"X_{avion['id']}_{f}" for f in range(franjas)]
    def restriccion(*asignaciones):
        tareas_tipo2_realizadas = 0
        tareas_tipo1_realizadas = 0
        realizando_t2 = avion['tareas_tipo2'] > 0
        for asignacion in asignaciones:
            if 'SPC' in asignacion:
                if tareas_tipo2_realizadas < avion['tareas_tipo2']:
                    tareas_tipo2_realizadas += 1
                elif tareas_tipo1_realizadas < avion['tareas_tipo1']:
                    if avion['restriccion_orden'] and realizando_t2:
                        return False
                    tareas_tipo1_realizadas += 1
                else:
                    pass
            elif 'STD' in asignacion:
                if tareas_tipo1_realizadas < avion['tareas_tipo1']:
                    if avion['restriccion_orden'] and realizando_t2:
                        return False
                    tareas_tipo1_realizadas += 1
                else:
                    pass
            elif 'PRK' in asignacion:
                if tareas_tipo2_realizadas < avion['tareas_tipo2'] or tareas_tipo1_realizadas < avion['tareas_tipo1']:
                    return False
            else:
                return False
            if tareas_tipo2_realizadas == avion['tareas_tipo2']:
                realizando_t2 = False
        if tareas_tipo2_realizadas != avion['tareas_tipo2']:
            return False
        if tareas_tipo1_realizadas != avion['tareas_tipo1']:
            return False
        return True
    problem.addConstraint(restriccion, variables_avion)

def generar_archivo_salida(nombre_archivo, soluciones, aviones, franjas, total_soluciones):
    with open(nombre_archivo, 'w') as archivo:
        archivo.write(f"N. Sol: {total_soluciones}\n")
        for idx, solucion in enumerate(soluciones, 1):
            archivo.write(f"Solución {idx}:\n")
            for avion in aviones:
                linea_avion = f"{avion['id']}-{avion['tipo']}-{'T' if avion['restriccion_orden'] else 'F'}-{avion['tareas_tipo1']}-{avion['tareas_tipo2']}: "
                for f in range(franjas):
                    nombre_variable = f"X_{avion['id']}_{f}"
                    asignacion = solucion[nombre_variable]
                    linea_avion += f"{asignacion} "
                archivo.write(linea_avion.strip() + "\n")
            archivo.write("\n")

if __name__ == "__main__":
    # Obtener la ruta del archivo de entrada desde los argumentos de línea de comandos
    if len(sys.argv) != 2:
        print("Uso: python CSPMaintenance.py <ruta_archivo_entrada>")
        sys.exit(1)

    ruta_archivo = sys.argv[1]

    print("Iniciando programa...")
    # Leer datos del archivo de entrada
    franjas, matriz_tamano, talleres_std, talleres_spc, parkings, aviones = leer_archivo_entrada(ruta_archivo)
    filas, columnas = matriz_tamano
    print("Archivo de entrada leído con éxito.")

    # Crear instancia del problema CSP
    problem = Problem()

    # Crear variables y dominios
    for avion in aviones:
        for f in range(franjas):
            nombre_variable = f"X_{avion['id']}_{f}"
            dominio = determinar_dominio(avion, f, franjas, talleres_std, talleres_spc, parkings)
            problem.addVariable(nombre_variable, dominio)

    # Agregar restricciones
    restriccion_capacidad_taller(problem, talleres_std, talleres_spc, aviones, franjas)

    # Generar diccionario de posiciones y adyacencias
    posiciones_dict = {}
    todas_posiciones = [("STD", pos) for pos in talleres_std] + \
                       [("SPC", pos) for pos in talleres_spc] + \
                       [("PRK", pos) for pos in parkings]

    for tipo, (x, y) in todas_posiciones:
        posicion_str = f"{tipo}({x},{y})"
        adyacentes = []
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < filas and 0 <= ny < columnas:
                for t, p in todas_posiciones:
                    if p == (nx, ny):
                        adyacentes.append(f"{t}({nx},{ny})")
        posiciones_dict[posicion_str] = adyacentes

    # Restricción de espacios adyacentes libres
    restriccion_adyacencia(problem, aviones, franjas, posiciones_dict)

    # Restricción de aviones JUMBO no adyacentes
    aviones_jumbo = [avion for avion in aviones if avion['tipo'] == 'JMB']
    restriccion_jumbos_no_adyacentes(problem, aviones_jumbo, franjas, posiciones_dict)

    # Agregar restricciones de tareas y orden
    for avion in aviones:
        restriccion_tareas_y_orden(problem, avion, franjas)

    # Resolver el problema
    max_solutions = 3  # Número máximo de soluciones a procesar
    soluciones = []
    solucion_iter = problem.getSolutionIter()
    contador_soluciones = 0

    for solucion in solucion_iter:
        soluciones.append(solucion)
        contador_soluciones += 1
        if contador_soluciones >= max_solutions:
            break

    # Verificar si hay más soluciones
    hay_mas_soluciones = False
    try:
        next(solucion_iter)
        hay_mas_soluciones = True
    except StopIteration:
        pass

    nombre_archivo_salida = os.path.splitext(os.path.basename(ruta_archivo))[0] + ".csv"

    if not soluciones:
        print("No se encontraron soluciones.")
        with open(nombre_archivo_salida, 'w') as archivo:
            archivo.write("N. Sol: 0\n")
    else:
        total_soluciones = contador_soluciones + (1 if hay_mas_soluciones else 0)
        print(f"Se encontraron {total_soluciones} soluciones.")
        generar_archivo_salida(nombre_archivo_salida, soluciones, aviones, franjas, total_soluciones)
        print(f"Archivo de salida generado: {nombre_archivo_salida}")